from __future__ import annotations

import re
from html import unescape
from typing import Any

from app.models.schemas import AbilityStoneSummary, CharacterSummary, EquipmentItem
from app.utils.tooltip import first_float, first_int, normalize_text, parse_tooltip

ACCESSORY_TYPES = {"목걸이", "귀걸이", "반지", "팔찌"}
STONE_TYPES = {"어빌리티 스톤"}
GEAR_TYPES = {"무기", "투구", "상의", "하의", "장갑", "어깨", "견갑"}
EXCLUDED_EQUIPMENT_TYPES = {"나침반", "부적", "보주"}

NEGATIVE_WORDS = ["공격력 감소", "공격속도 감소", "방어력 감소", "이동속도 감소", "감소"]
STONE_SKIP_WORDS = [
    "Element", "value", "leftStr", "rightStr", "contentStr", "아이템", "효과", "툴팁", "거래", "가능", "품질",
    "어빌리티", "스톤", "등급", "레벨", "세공", "확률", "성공", "실패", "활성도", "기본", "추가",
]



BRACELET_SPECIAL_EFFECTS = [
    # 딜러/공용 특수 효과
    "쐐기", "망치", "순환", "정밀", "습격", "우월", "열정", "냉정", "상처악화",
    "기습", "결투", "강타", "마무리", "분개", "돌진", "멸시", "타격",
    # 서포터/유틸 계열
    "비수", "약점 노출", "응원", "깨달음", "앵콜", "긴급수혈", "마나회수", "응급처치",
    "투자", "반격", "보상",
]

BRACELET_EFFECT_KEYWORDS = [
    "치명", "특화", "신속", "제압", "인내", "숙련",
    "힘", "민첩", "지능", "체력", "최대 생명력",
    "공격력", "무기 공격력", "치명타", "피해", "추가 피해",
    *BRACELET_SPECIAL_EFFECTS,
]


BRACELET_SECTION_TITLES = ["팔찌 부여 효과 상세", "고정 효과", "부여 효과"]


def _htmlish_lines(value: Any) -> list[str]:
    if value is None:
        return []
    raw = str(value)
    raw = unescape(raw)
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    raw = re.sub(r"</p>|</div>|</li>", "\n", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = raw.replace('\r', '\n')
    lines = []
    for line in raw.split('\n'):
        clean = re.sub(r"\s+", " ", line).strip()
        if clean:
            lines.append(clean)
    return lines


def _normalize_bracelet_line(text: str, section: str | None = None) -> str:
    text = _clean_bracelet_effect_text(text)
    if not text:
        return ''
    text = re.sub(r'^(고정 효과|부여 효과)\s*[:：-]?\s*', '', text)

    # Compact common long descriptions but preserve the key value.
    text = text.replace('스킬의 재사용 대기 시간이', '스킬 재사용 대기시간')
    text = text.replace('스킬의 재사용 대기시간이', '스킬 재사용 대기시간')
    text = text.replace('적에게 주는 피해가 증가', '피해 증가')
    text = text.replace('공격에 의한 스킬이 적에게 주는 피해가 증가', '공격 피해 증가')
    text = text.replace('가 적용되지 않는다', ' 미적용')
    text = text.replace('는 적용되지 않는다', ' 미적용')

    # Normalize stat lines.
    m = re.match(r'^(상|중|하)\s*(치명|특화|신속|제압|인내|숙련|힘|민첩|지능|체력|최대 생명력|공격력|무기 공격력)\s*([+＋-]?\d[\d,]*(?:\.\d+)?%?)$', text)
    if m:
        return f"{m.group(1)} {m.group(2)} {m.group(3)}"

    # Keep labelled effect lines like '중 무기 공격력 +8100' or long special descriptions.
    m = re.match(r'^(상|중|하)\s*(.+)$', text)
    if m:
        grade, body = m.group(1), m.group(2).strip()
        body = re.sub(r'\s+', ' ', body)
        # Shorten a few very long descriptions while keeping meaning.
        if '스킬 재사용 대기시간' in body and '피해 증가' in body:
            nums = re.findall(r'(\d+(?:\.\d+)?)\s*%', body)
            if len(nums) >= 2:
                body = f"스킬 재사용 대기시간 {nums[0]}% / 피해 증가 {nums[1]}%"
        elif '방랑형 공격' in body and '피해' in body:
            nums = re.findall(r'(\d+(?:\.\d+)?)\s*%', body)
            if nums:
                body = f"방랑형 공격 피해 증가 {nums[0]}%"
        elif len(body) > 70:
            # Try to preserve first meaningful phrase and any nearby percentage.
            nums = re.findall(r'(\d+(?:\.\d+)?)\s*%', body)
            first = body[:46].rstrip(' ,')
            body = f"{first}{(' ' + nums[0] + '%') if nums else ''}"
        return f"{grade} {body}"

    # Section-prefixed fallback when useful.
    if section in {'고정 효과', '부여 효과'} and any(k in text for k in BRACELET_EFFECT_KEYWORDS):
        return text
    return text


def _extract_bracelet_effects_from_sections(tooltip_obj: dict[str, Any]) -> list[str]:
    effects: list[str] = []
    current_section: str | None = None

    def add(raw_line: str):
        line = _normalize_bracelet_line(raw_line, current_section)
        if not line:
            return
        if line in BRACELET_SECTION_TITLES:
            return
        if any(skip in line for skip in ['거래', '분해', '판매', '착용', '귀속', '아이템 레벨', '품질', '세공', '재련']):
            return
        if line not in effects:
            effects.append(line)

    for _key, value in _walk(tooltip_obj):
        if not isinstance(value, str):
            continue
        lines = _htmlish_lines(value)
        for line in lines:
            if line in BRACELET_SECTION_TITLES:
                if line != '팔찌 부여 효과 상세':
                    current_section = line
                continue
            if '고정 효과' == line or line.startswith('고정 효과'):
                current_section = '고정 효과'
                continue
            if '부여 효과' == line or line.startswith('부여 효과'):
                current_section = '부여 효과'
                continue
            # Accept only lines that resemble bracelet effects.
            if re.match(r'^(상|중|하)\s*', line) or any(k in line for k in BRACELET_EFFECT_KEYWORDS):
                add(line)
    return effects



ACCESSORY_POLISH_EFFECT_KEYWORDS = [
    "추가 피해", "적에게 주는 피해", "피해", "무기 공격력", "공격력",
    "치명타 적중률", "치명타 피해", "치명타", "공격 속도", "이동 속도",
    "낙인력", "아군 공격력", "아군 피해", "보호막", "생명력", "최대 생명력",
    "최대 마나", "전투 중 생명력 회복", "마나 회복", "파티원",
]


def _clean_accessory_effect_text(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    text = re.sub(r"^(?:Element_\d+|value|leftStr|rightStr|contentStr|topStr)\s*", "", text)
    text = re.sub(r"^(?:장신구|장신구 연마|연마 효과|부여 효과|옵션 효과)\s*[:：-]?\s*", "", text)
    text = re.sub(r"[\[\]{}\"]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -•|:/")
    return text


def _normalize_accessory_effect_line(text: str) -> str:
    text = _clean_accessory_effect_text(text)
    if not text:
        return ""
    if any(skip in text for skip in ["아이템 레벨", "품질", "거래", "분해", "판매", "착용", "귀속", "아크 패시브", "깨달음"]):
        return ""
    text = text.replace("적에게 주는 피해가", "피해")
    text = text.replace("증가합니다", "증가")
    text = text.replace("증가한다", "증가")
    text = text.replace("감소합니다", "감소")
    text = text.replace("감소한다", "감소")
    text = text.replace("치명타 적중률이", "치명타 적중률")
    text = text.replace("치명타 피해가", "치명타 피해")
    text = re.sub(r"\s+", " ", text).strip()

    # Keep short grade-prefixed effect lines, e.g. '상 추가 피해 +2.60%'.
    m = re.match(r"^(상|중|하)\s*(.+)$", text)
    if m:
        grade, body = m.group(1), m.group(2).strip()
        nums = re.findall(r"[+＋-]?\d+(?:\.\d+)?\s*%?", body)
        # Long descriptions are shortened but keep one key number.
        if len(body) > 80:
            key = next((k for k in ACCESSORY_POLISH_EFFECT_KEYWORDS if k in body), body[:28])
            body = f"{key} {nums[0]}" if nums else key
        return f"{grade} {body}"

    # Non grade-prefixed lines must still look like an actual effect.
    if not any(k in text for k in ACCESSORY_POLISH_EFFECT_KEYWORDS):
        return ""
    if len(text) > 90:
        nums = re.findall(r"[+＋-]?\d+(?:\.\d+)?\s*%?", text)
        key = next((k for k in ACCESSORY_POLISH_EFFECT_KEYWORDS if k in text), text[:28])
        return f"{key} {nums[0]}" if nums else key
    return text


def _extract_accessory_polish_effects(tooltip_obj: dict[str, Any], tooltip_text: str) -> list[str]:
    effects: list[str] = []

    def add(raw: Any) -> None:
        line = _normalize_accessory_effect_line(str(raw))
        if line and line not in effects:
            effects.append(line)

    # Structured tooltip blocks often contain leftStr/rightStr pairs for options.
    for _key, value in _walk(tooltip_obj):
        if not isinstance(value, str):
            continue
        raw = value
        # Split HTML-ish text into shorter lines.
        for line in re.split(r"<br\s*/?>|\\n|\n|</p>|</div>", raw, flags=re.I):
            if any(k in normalize_text(line) for k in ACCESSORY_POLISH_EFFECT_KEYWORDS + ["연마"]):
                add(line)

    text_full = normalize_text(tooltip_text)
    # Fallback patterns for common T4 accessory polishing effect lines.
    patterns = [
        r"(상|중|하)\s*([^|{}\[\]]{0,40}?(?:추가 피해|피해|무기 공격력|공격력|치명타 적중률|치명타 피해|낙인력|아군 공격력|아군 피해|보호막|최대 생명력)[^|{}\[\]]{0,45})",
        r"((?:추가 피해|적에게 주는 피해|무기 공격력|공격력|치명타 적중률|치명타 피해|낙인력|아군 공격력|아군 피해|보호막|최대 생명력)[^|{}\[\]]{0,45}[+＋-]?\d+(?:\.\d+)?\s*%?)",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, text_full):
            add(" ".join(x for x in m.groups() if x))

    # Remove duplicate substrings and aggregate tooltip lines.
    # Lost Ark tooltip sometimes contains both separate effect rows and one concatenated row such as
    # "공격력 +80 무기 공격력 +1.80% 공격력 +0.95%". The concatenated row makes the UI duplicate
    # effects and inflates valid-effect counting, so drop multi-number aggregate rows when the shorter
    # rows are already present.
    cleaned: list[str] = []
    for effect in effects:
        if len(effect) < 2:
            continue
        numbers = re.findall(r"[+＋-]?\d+(?:\.\d+)?\s*%?", effect)
        keyword_hits = [k for k in ACCESSORY_POLISH_EFFECT_KEYWORDS if k in effect]
        looks_aggregate = len(numbers) >= 2 and len(set(keyword_hits)) >= 2
        if looks_aggregate:
            # Keep it only if it is not clearly represented by shorter parsed rows.
            has_short_duplicate = any(short != effect and short in effect for short in effects)
            if has_short_duplicate:
                continue
        if effect not in cleaned:
            cleaned.append(effect)
    return cleaned[:8]


def _clean_bracelet_effect_text(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    # Remove common label noise from tooltip JSON blocks.
    text = re.sub(r"^(?:Element_\d+|value|leftStr|rightStr|contentStr|topStr)\s*", "", text)
    text = re.sub(r"^(?:팔찌|팔찌 효과|특수 효과|기본 효과|부여 효과)\s*[:：-]?\s*", "", text)
    text = re.sub(r"[\[\]{}\"]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -•|:/")
    return text


def _compact_special_effect(text: str) -> str:
    """Return a short display string for bracelet special effects.

    Some bracelet tooltip blocks contain a whole sentence, for example
    '순환: ... 30초마다 ...'. Showing that entire sentence makes the table unreadable,
    so we compress it to '순환' or '순환 3.5%' when a nearby numeric value exists.
    """
    clean = _clean_bracelet_effect_text(text)
    if not clean:
        return ""
    for name in BRACELET_SPECIAL_EFFECTS:
        idx = clean.find(name)
        if idx < 0:
            continue
        window = clean[idx: idx + 90]
        grade_match = re.search(rf"{re.escape(name)}\s*([상중하])", window)
        pct_match = re.search(r"([0-9]+(?:\.\d+)?)\s*%", window)
        if grade_match and pct_match:
            return f"{name} {grade_match.group(1)} {pct_match.group(1)}%"
        if grade_match:
            return f"{name} {grade_match.group(1)}"
        if pct_match:
            return f"{name} {pct_match.group(1)}%"
        return name
    return ""


def _extract_bracelet_effects(tooltip_obj: dict[str, Any], tooltip_text: str) -> list[str]:
    """Extract readable bracelet effects from Lost Ark tooltip JSON/text.

    Prefer the explicit bracelet detail section when present, because it contains
    lines such as `상 치명 +109`, `중 무기 공격력 +8100`, `하 방랑형 공격 ...`.
    """
    effects: list[str] = _extract_bracelet_effects_from_sections(tooltip_obj)

    def add_effect(raw: Any) -> None:
        text = _clean_bracelet_effect_text(raw)
        if not text:
            return
        if any(skip in text for skip in [
            "아이템 레벨", "품질", "거래", "분해", "판매", "착용", "귀속",
            "팔찌 효과 부여", "효과 변환", "새겨진", "세공", "재련", "장착",
        ]):
            return

        compact = _compact_special_effect(text)
        if compact:
            if compact not in effects:
                effects.append(compact)
            return

        if len(text) > 120:
            return
        if not any(keyword in text for keyword in BRACELET_EFFECT_KEYWORDS):
            return

        # Keep numeric base effects only when a value exists.
        has_number = bool(re.search(r"[+＋]?\d+(?:\.\d+)?\s*(?:%|초|회)?", text))
        if not has_number:
            return
        if text not in effects:
            effects.append(text)

    # Prefer direct strings from tooltip blocks.
    for _key, value in _walk(tooltip_obj):
        if isinstance(value, str):
            add_effect(value)

    # Regex fallbacks from the full normalized tooltip text.
    text = normalize_text(tooltip_text)
    stat_pattern = r"(치명|특화|신속|제압|인내|숙련|힘|민첩|지능|체력|최대 생명력|공격력|무기 공격력)\s*[+＋]?\s*([0-9,]+(?:\.\d+)?)"
    for m in re.finditer(stat_pattern, text):
        add_effect(f"{m.group(1)} +{m.group(2)}")

    # Special bracelet effects often appear in long sentences. Capture their name even if the value is not close.
    for name in BRACELET_SPECIAL_EFFECTS:
        if name in text:
            add_effect(name)

    percent_pattern = rf"({'|'.join(re.escape(x) for x in BRACELET_SPECIAL_EFFECTS)})[^0-9%]{{0,40}}([0-9]+(?:\.\d+)?)\s*%?"
    for m in re.finditer(percent_pattern, text):
        add_effect(f"{m.group(1)} {m.group(2)}%")

    return effects[:15]


def _num_from_level(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    if not m:
        return None
    return float(m.group(1))


def _pick(data: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in data:
            return data[k]
    return None


def _walk(obj: Any):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key, value
            yield from _walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk(value)


def _extract_quality(tooltip_obj: dict[str, Any], tooltip_text: str) -> int | None:
    """Prefer structured qualityValue and only accept real 0~100 quality values."""
    candidates: list[int] = []
    for key, value in _walk(tooltip_obj):
        key_l = str(key).lower()
        if isinstance(value, (int, float)) and ("quality" in key_l or "품질" in str(key)):
            ivalue = int(value)
            if 0 <= ivalue <= 100:
                candidates.append(ivalue)
        if isinstance(value, str) and ("quality" in key_l or "품질" in str(key)):
            m = re.search(r"(\d{1,3})", value)
            if m:
                ivalue = int(m.group(1))
                if 0 <= ivalue <= 100:
                    candidates.append(ivalue)

    if candidates:
        return max(candidates)

    patterns = [
        r'qualityValue["\s:]+(\d{1,3})',
        r'품질\s*[:：]?\s*(\d{1,3})(?!\s*단계)',
        r'품질[^0-9]{0,8}(\d{1,3})(?:\s*/\s*100|\s*점)',
    ]
    for pattern in patterns:
        m = re.search(pattern, tooltip_text)
        if m:
            ivalue = int(m.group(1))
            if 0 <= ivalue <= 100:
                return ivalue
    return None


def _clean_stone_name(name: str) -> str:
    name = normalize_text(name)
    name = re.sub(r"(?:Element_\d+|value|leftStr|rightStr|contentStr|topStr|bPoint|무작위|각인|효과|활성도|Lv\.?\s*\d*)", " ", name)
    name = re.sub(r"[^가-힣A-Za-z\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _valid_stone_name(name: str) -> bool:
    if len(name) < 2 or len(name) > 24:
        return False
    if not re.search(r"[가-힣]", name):
        return False
    return not any(skip in name for skip in STONE_SKIP_WORDS)



def _normalize_slot(slot: str, name: Any = None) -> str:
    """Normalize Lost Ark equipment slot names safely.

    Do not search every gear word in the combined `slot + name` string.
    Ability stone names such as "위대한 비상의 돌" contain the substring
    "상의", so the old logic misclassified that stone as an upper-body armor.
    We now trust the API Type field first, and only use the item name as a
    cautious fallback for ability stones.
    """
    slot_text = normalize_text(slot)
    name_text = normalize_text(name)

    # Ability stone must be checked before armor words.
    if "어빌리티" in slot_text and "스톤" in slot_text:
        return "어빌리티 스톤"
    if slot_text in {"어빌리티 스톤", "스톤"}:
        return "어빌리티 스톤"

    # Exact/slot-field based matching for normal gear.
    if "무기" in slot_text:
        return "무기"
    if "투구" in slot_text or "머리" in slot_text:
        return "투구"
    if slot_text == "상의" or slot_text.endswith("상의"):
        return "상의"
    if slot_text == "하의" or slot_text.endswith("하의"):
        return "하의"
    if "장갑" in slot_text:
        return "장갑"
    if "어깨" in slot_text or "견갑" in slot_text:
        return "어깨"

    # Accessory slots.
    if "목걸이" in slot_text:
        return "목걸이"
    if "귀걸이" in slot_text:
        return "귀걸이"
    if "반지" in slot_text:
        return "반지"
    if "팔찌" in slot_text:
        return "팔찌"

    if "나침반" in slot_text:
        return "나침반"
    if "부적" in slot_text:
        return "부적"
    if "보주" in slot_text:
        return "보주"

    # Fallback: stone names commonly end with 돌, but avoid using name text
    # for armor/accessory words because names can contain misleading substrings.
    if name_text.endswith("돌") and ("스톤" in slot_text or "어빌리티" in slot_text or not slot_text):
        return "어빌리티 스톤"

    return slot_text or "알 수 없음"


def _extract_honing_level(name: Any, tooltip_text: str) -> int | None:
    # 장비명에 붙은 +19가 가장 신뢰도 높다.
    name_text = normalize_text(name)
    for pattern in [r"^\s*\+(\d{1,2})", r"\s\+(\d{1,2})(?:\s|$)", r"재련\s*(\d{1,2})\s*단계"]:
        m = re.search(pattern, name_text)
        if m:
            value = int(m.group(1))
            if 0 <= value <= 25:
                return value

    # Tooltip에서는 반드시 재련/강화 문맥이 있는 숫자만 사용한다.
    text = normalize_text(tooltip_text)
    patterns = [
        r"재련\s*단계[^0-9+＋]{0,12}[+＋]?(\d{1,2})",
        r"강화\s*단계[^0-9+＋]{0,12}[+＋]?(\d{1,2})",
        r"[+＋](\d{1,2})\s*(?:재련|강화)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            value = int(m.group(1))
            if 0 <= value <= 25:
                return value
    return None


def _extract_item_level(tooltip_text: str) -> float | None:
    text = normalize_text(tooltip_text)
    patterns = [
        r"아이템\s*레벨[^0-9]*(\d+(?:\.\d+)?)",
        r"Item\s*Level[^0-9]*(\d+(?:\.\d+)?)",
        r"아이템\s*Lv\.?[^0-9]*(\d+(?:\.\d+)?)",
    ]
    return first_float(patterns, text)

def parse_equipment_item(raw: dict[str, Any]) -> EquipmentItem:
    raw_slot = str(_pick(raw, "Type", "type") or "알 수 없음")
    name = _pick(raw, "Name", "name")
    slot = _normalize_slot(raw_slot, name)
    grade = _pick(raw, "Grade", "grade")
    tooltip_obj, tooltip_text = parse_tooltip(_pick(raw, "Tooltip", "tooltip"))

    honing = _extract_honing_level(name, tooltip_text)
    quality = _extract_quality(tooltip_obj, tooltip_text)
    item_level = _extract_item_level(tooltip_text)

    # Current accessory table does not show these, but keep parsed values internally for later extensions.
    polish_level = first_int([r"연마\s*(\d)\s*단계", r"(\d)\s*단계\s*연마"], tooltip_text)
    enlightenment = first_int([r"깨달음[^0-9]*(\d+)", r"아크\s*패시브[^0-9]*(\d+)"], tooltip_text)

    bracelet_effects = _extract_bracelet_effects(tooltip_obj, tooltip_text) if slot == "팔찌" else []
    accessory_effects = _extract_accessory_polish_effects(tooltip_obj, tooltip_text) if slot in ACCESSORY_TYPES and slot != "팔찌" else []

    return EquipmentItem(
        slot=slot,
        name=name,
        grade=grade,
        item_level=item_level,
        honing_level=honing,
        quality=quality,
        is_accessory=slot in ACCESSORY_TYPES,
        polish_level=polish_level,
        enlightenment_points=enlightenment,
        # Keep a longer excerpt because ability stone engraving lines often appear deep inside the JSON tooltip.
        raw_tooltip_excerpt=tooltip_text[:30000] if tooltip_text else None,
        bracelet_effects=bracelet_effects,
        accessory_effects=accessory_effects,
    )


def _dedupe_pairs(pairs: list[tuple[str, int]]) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for raw_name, point in pairs:
        name = _clean_stone_name(raw_name)
        if not _valid_stone_name(name):
            continue
        if not (0 <= int(point) <= 10):
            continue
        key = (name, int(point))
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _parse_stone_pairs_from_text(text: str) -> list[tuple[str, int]]:
    text = normalize_text(text)
    if not text:
        return []

    pairs: list[tuple[str, int]] = []

    patterns = [
        # leftStr0 원한 rightStr0 활성도 +7
        r"leftStr\d*\s+(.{2,80}?)\s+rightStr\d*\s+(?:\[?활성도\]?|활성 포인트|포인트)?\s*[+＋]?\s*(\d{1,2})",
        # 원한 Lv. 3 활성도 +7 / 원한 활성도 +7
        r"([가-힣][가-힣A-Za-z\s]{1,24}?)(?:\s+Lv\.?\s*\d+)?\s+(?:\[?활성도\]?|활성 포인트|포인트)\s*[+＋]?\s*(\d{1,2})",
        # 원한 : 활성도 7 / 원한 : 7 활성도
        r"([가-힣][가-힣A-Za-z\s]{1,24}?)\s*[:：]\s*(?:활성도\s*)?[+＋]?\s*(\d{1,2})",
        # 원한 [7] / 원한 (7)  - 스톤 툴팁 내부에서만 후처리로 사용
        r"([가-힣][가-힣A-Za-z\s]{1,24}?)\s*[\[\(]\s*(\d{1,2})\s*[\]\)]",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, text):
            context = text[max(0, m.start() - 80):m.end() + 80]
            if any(bad in context for bad in ["품질", "아이템 레벨", "티어", "거래", "초월", "연마", "구매", "판매"]):
                continue
            pairs.append((m.group(1), int(m.group(2))))

    # 활성도 +7 원한
    for m in re.finditer(
        r"(?:\[?활성도\]?|활성 포인트|포인트)\s*[+＋]?\s*(\d{1,2})\s+([가-힣][가-힣A-Za-z\s]{1,24})",
        text,
    ):
        pairs.append((m.group(2), int(m.group(1))))

    # contentStr 원한 +7 등. 스톤 관련 문맥 안에서만 사용한다.
    for m in re.finditer(r"([가-힣][가-힣A-Za-z\s]{1,24}?)\s*[+＋]\s*(\d{1,2})(?!\d)", text):
        context = text[max(0, m.start() - 90):m.end() + 40]
        if not any(ok in context for ok in ["각인", "활성", "어빌리티", "스톤"]):
            continue
        if any(bad in context for bad in ["품질", "아이템 레벨", "티어", "거래", "초월", "연마"]):
            continue
        pairs.append((m.group(1), int(m.group(2))))

    return _dedupe_pairs(pairs)

def _parse_stone_pairs_from_obj(obj: Any) -> list[tuple[str, int]]:
    # Use local left/right string groups when present; this avoids pulling all active engravings from unrelated API sections.
    pairs: list[tuple[str, int]] = []
    if isinstance(obj, dict):
        left = obj.get("leftStr") or obj.get("LeftStr") or obj.get("left")
        right = obj.get("rightStr") or obj.get("RightStr") or obj.get("right")
        if left is None or right is None:
            for k, v in obj.items():
                if re.fullmatch(r"leftStr\d*", str(k)):
                    left = v
                if re.fullmatch(r"rightStr\d*", str(k)):
                    right = v
        if left is not None and right is not None:
            right_text = normalize_text(right)
            m = re.search(r"활성도\s*[+＋]?\s*(\d{1,2})", right_text)
            if m:
                pairs.append((normalize_text(left), int(m.group(1))))
        for _key, value in obj.items():
            pairs.extend(_parse_stone_pairs_from_obj(value))
    elif isinstance(obj, list):
        for value in obj:
            pairs.extend(_parse_stone_pairs_from_obj(value))
    elif isinstance(obj, str):
        pairs.extend(_parse_stone_pairs_from_text(obj))
    return _dedupe_pairs(pairs)



def _parse_stone_pairs_from_raw_tooltip(raw: dict[str, Any]) -> list[tuple[str, int]]:
    tooltip_obj, tooltip_text = parse_tooltip(_pick(raw, "Tooltip", "tooltip"))
    pairs = []
    pairs.extend(_parse_stone_pairs_from_obj(tooltip_obj))
    pairs.extend(_parse_stone_pairs_from_text(tooltip_text))

    # Additional block-level fallback. Some tooltip blocks contain an engraving name and a point
    # in separate nested strings without using leftStr/rightStr. We only examine the stone tooltip.
    for _key, value in _walk(tooltip_obj):
        block = normalize_text(value)
        if not block or not any(token in block for token in ["각인", "활성", "어빌리티", "스톤"]):
            continue
        pairs.extend(_parse_stone_pairs_from_text(block))

    return _dedupe_pairs(pairs)


def _extract_stone_points_fallback(raw_text: str) -> tuple[list[int], int | None]:
    """각인 이름 파싱이 실패해도 7/7 같은 스톤 결과만 얻기 위한 fallback.

    로아 API의 Tooltip은 캐릭터/시점별로 HTML, JSON, leftStr/rightStr 구조가 조금씩 다릅니다.
    서비스 계산에는 각인 이름보다 포인트 조합이 중요하므로, 활성도 숫자만 안정적으로 뽑습니다.
    """
    text = normalize_text(raw_text)
    positive: list[int] = []
    negative: list[int] = []
    for m in re.finditer(r"(?:활성도|활성\s*포인트|포인트)\s*[+＋]?\s*(\d{1,2})", text):
        point = int(m.group(1))
        context = text[max(0, m.start() - 160):m.end() + 80]
        if point > 10:
            continue
        if any(word in context for word in NEGATIVE_WORDS):
            negative.append(point)
        else:
            positive.append(point)

    # 일부 툴팁은 "각인명 +7"만 남아 있다. 어빌리티 스톤 문맥 안에서만 보조 사용.
    if len(positive) < 2:
        for m in re.finditer(r"([가-힣][가-힣A-Za-z\s]{1,24}?)\s*[+＋]\s*(\d{1,2})(?!\d)", text):
            point = int(m.group(2))
            context = text[max(0, m.start() - 120):m.end() + 80]
            if point > 10 or not any(ok in context for ok in ["어빌리티", "스톤", "각인", "활성"]):
                continue
            if any(bad in context for bad in ["품질", "아이템 레벨", "거래", "연마", "초월"]):
                continue
            if any(word in context for word in NEGATIVE_WORDS):
                negative.append(point)
            else:
                positive.append(point)

    positive = sorted(list({p for p in positive if 0 <= p <= 10}), reverse=True)
    negative = sorted(list({p for p in negative if 0 <= p <= 10}), reverse=True)
    return positive[:2], (negative[0] if negative else None)


def _parse_stone_from_engravings(engravings: dict[str, Any] | None) -> tuple[list[tuple[str, int]], list[int], int | None]:
    """ArmoryEngraving의 ArkPassiveEffects 보조 파싱.

    pyLoa 모델에도 ArkPassiveEffect.ability_stone_level 필드가 존재하므로,
    API가 해당 값을 내려주는 경우 스톤 포인트 보정에 사용한다.
    """
    if not isinstance(engravings, dict):
        return [], [], None
    pairs: list[tuple[str, int]] = []
    for item in engravings.get("ArkPassiveEffects") or []:
        if not isinstance(item, dict):
            continue
        name = normalize_text(item.get("Name"))
        level = item.get("AbilityStoneLevel")
        try:
            point = int(level)
        except Exception:
            continue
        if point <= 0 or point > 10 or not name:
            continue
        pairs.append((name, point))
    positive, negative = _classify_stone_pairs(pairs)
    return pairs, [p for _, p in positive[:2]], (negative[0][1] if negative else None)


def _build_stone_summary(
    stone_item: EquipmentItem,
    pairs: list[tuple[str, int]],
    fallback_positive_points: list[int] | None = None,
    fallback_negative_point: int | None = None,
) -> AbilityStoneSummary:
    positive, negative = _classify_stone_pairs(pairs)
    p1 = positive[0] if len(positive) >= 1 else (None, None)
    p2 = positive[1] if len(positive) >= 2 else (None, None)
    neg = negative[0] if negative else (None, None)

    fallback_positive_points = fallback_positive_points or []
    if p1[1] is None and len(fallback_positive_points) >= 1:
        p1 = (p1[0] or "각인 1", int(fallback_positive_points[0]))
    if p2[1] is None and len(fallback_positive_points) >= 2:
        p2 = (p2[0] or "각인 2", int(fallback_positive_points[1]))
    if neg[1] is None and fallback_negative_point is not None:
        neg = (neg[0] or "감소", int(fallback_negative_point))

    stone_type = None
    if isinstance(p1[1], int) and isinstance(p2[1], int):
        high, low = sorted([p1[1], p2[1]], reverse=True)
        stone_type = f"{high}/{low}"

    return AbilityStoneSummary(
        name=stone_item.name,
        grade=stone_item.grade,
        positive_1_name=p1[0],
        positive_1_points=p1[1],
        positive_2_name=p2[0],
        positive_2_points=p2[1],
        negative_name=neg[0],
        negative_points=neg[1],
        stone_type=stone_type,
        quality=stone_item.quality,
        raw_tooltip_excerpt=stone_item.raw_tooltip_excerpt,
    )

def _classify_stone_pairs(pairs: list[tuple[str, int]]) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    positive: list[tuple[str, int]] = []
    negative: list[tuple[str, int]] = []
    for name, point in pairs:
        if any(word in name for word in NEGATIVE_WORDS):
            negative.append((name, point))
        else:
            positive.append((name, point))
    # If duplicated active engravings appear, keep the highest point per name.
    def compress(items: list[tuple[str, int]]) -> list[tuple[str, int]]:
        best: dict[str, int] = {}
        for n, p in items:
            best[n] = max(best.get(n, -1), p)
        return sorted(best.items(), key=lambda x: x[1], reverse=True)
    return compress(positive), compress(negative)


def parse_ability_stone(
    equipment: list[EquipmentItem],
    raw_equipment: list[dict[str, Any]] | None = None,
    raw_engravings: dict[str, Any] | None = None,
) -> AbilityStoneSummary | None:
    stone_item = next((x for x in equipment if x.slot in STONE_TYPES or (x.name and "어빌리티" in x.name)), None)
    if not stone_item:
        return None

    pairs: list[tuple[str, int]] = []
    fallback_positive: list[int] = []
    fallback_negative: int | None = None
    raw_stone_text = stone_item.raw_tooltip_excerpt or ""

    if raw_equipment:
        raw_stone = next((x for x in raw_equipment if isinstance(x, dict) and (str(_pick(x, "Type", "type")) in STONE_TYPES or "어빌리티" in str(_pick(x, "Name", "name") or ""))), None)
        if raw_stone:
            pairs.extend(_parse_stone_pairs_from_raw_tooltip(raw_stone))
            _obj, raw_stone_text = parse_tooltip(_pick(raw_stone, "Tooltip", "tooltip"))

    if not pairs:
        pairs.extend(_parse_stone_pairs_from_text(raw_stone_text))

    # pyLoa의 ArmoryEngraving/ArkPassiveEffects 구조를 보조 데이터로 활용한다.
    e_pairs, e_positive, e_negative = _parse_stone_from_engravings(raw_engravings)
    pairs.extend(e_pairs)
    fallback_positive.extend(e_positive)
    if e_negative is not None:
        fallback_negative = e_negative

    # 이름 기반 추출이 실패하면 활성도 숫자만 추출한다.
    if len(_classify_stone_pairs(pairs)[0]) < 2:
        f_pos, f_neg = _extract_stone_points_fallback(raw_stone_text)
        fallback_positive.extend(f_pos)
        if fallback_negative is None:
            fallback_negative = f_neg

    fallback_positive = sorted(list({p for p in fallback_positive if isinstance(p, int)}), reverse=True)[:2]
    return _build_stone_summary(stone_item, pairs, fallback_positive, fallback_negative)


def build_character_summary(bundle: dict[str, Any], raw_saved_path: str | None = None) -> CharacterSummary:
    profile = bundle.get("profile") or {}
    raw_equipment = bundle.get("equipment") or []

    equipment_items = [parse_equipment_item(x) for x in raw_equipment if isinstance(x, dict)]
    accessories = [x for x in equipment_items if x.is_accessory]
    gear = [x for x in equipment_items if x.slot in GEAR_TYPES and x.slot not in EXCLUDED_EQUIPMENT_TYPES]
    stone = parse_ability_stone(equipment_items, raw_equipment, bundle.get("engravings"))

    warnings: list[str] = []
    # Do not show noisy warning in the main UI. If parsing fails, the simulator uses a 7/7 default internally.
    if not accessories:
        warnings.append("장신구 정보를 찾지 못했습니다. 캐릭터 공개 정보 또는 API 응답을 확인하세요.")

    return CharacterSummary(
        character_name=_pick(profile, "CharacterName", "characterName") or "알 수 없음",
        server_name=_pick(profile, "ServerName", "serverName"),
        class_name=_pick(profile, "CharacterClassName", "characterClassName"),
        item_avg_level=_num_from_level(_pick(profile, "ItemAvgLevel", "itemAvgLevel")),
        character_level=_pick(profile, "CharacterLevel", "characterLevel"),
        equipment=gear,
        accessories=accessories,
        ability_stone=stone,
        warnings=warnings,
        raw_saved_path=raw_saved_path,
    )
