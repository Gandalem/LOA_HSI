from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.models.schemas import CharacterSummary, EquipmentItem


SUPPORT_CLASSES = {"바드", "도화가", "홀리나이트"}
COMBAT_STATS = ["치명", "특화", "신속", "제압", "인내", "숙련"]
BASIC_KEYWORDS = ["힘", "민첩", "지능", "체력", "최대 생명력", "물리 방어력", "마법 방어력"]
SPECIAL_EFFECTS = [
    "쐐기", "망치", "순환", "정밀", "습격", "우월", "열정", "냉정", "상처악화", "기습", "결투", "강타", "마무리", "분개", "돌진", "멸시", "타격",
    "비수", "약점 노출", "응원", "깨달음", "앵콜", "긴급수혈", "마나회수", "응급처치", "투자", "반격", "보상",
]
ROLE_SPECIALS = {
    "dealer": ["쐐기", "망치", "순환", "정밀", "습격", "우월", "열정", "냉정", "상처악화"],
    "support": ["비수", "약점 노출", "응원", "깨달음", "마나회수", "앵콜"],
}


def _config_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "config"
    if path.exists():
        return path
    return Path("/app/backend/config")


@lru_cache(maxsize=1)
def _official_table() -> dict[str, Any]:
    path = _config_dir() / "bracelet_t4_probabilities_official.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _role_key(character: CharacterSummary, class_preset: dict[str, Any] | None = None) -> str:
    role = str((class_preset or {}).get("role") or "")
    if role in {"support", "서포터"} or "서포터" in role:
        return "support"
    if str(character.class_name or "") in SUPPORT_CLASSES:
        return "support"
    return "dealer"


def _bracelet_grade(item: EquipmentItem | None) -> str:
    grade = str(item.grade if item else "" or "")
    if "유물" in grade:
        return "relic"
    return "ancient"


def _extract_number(effect: str) -> float | None:
    m = re.search(r"[+＋-]?\s*(\d+(?:\.\d+)?)", str(effect or ""))
    return float(m.group(1)) if m else None


def _category_key(effect: str) -> str:
    text = str(effect or "")
    if any(re.search(rf"{stat}\s*[+＋]", text) for stat in COMBAT_STATS):
        return "combatStat"
    if any(keyword in text for keyword in SPECIAL_EFFECTS):
        return "special"
    if any(keyword in text for keyword in BASIC_KEYWORDS):
        return "basic"
    # 팔찌 특수 효과는 툴팁 문장이 길게 표시되는 경우가 많아 미분류 문장은 특수 효과 후보로 보수 분류합니다.
    if "피해" in text or "공격" in text or "낙인" in text or "아군" in text or "마나" in text:
        return "special"
    return "unknown"


def _official_name(effect: str, category: str) -> str | None:
    text = str(effect or "")
    if category == "combatStat":
        return next((stat for stat in COMBAT_STATS if re.search(rf"{stat}\s*[+＋]", text)), None)
    if category == "basic":
        return next((keyword for keyword in BASIC_KEYWORDS if keyword in text), None)
    if category == "special":
        return next((keyword for keyword in SPECIAL_EFFECTS if keyword in text), None) or "특수 효과 문장"
    return None


def _match_role(effect: str, category: str, role: str, class_preset: dict[str, Any] | None = None) -> str:
    text = str(effect or "")
    preset_specials = [str(x) for x in ((class_preset or {}).get("braceletOptions") or (class_preset or {}).get("bracelet_options") or [])]
    preset_stats = [str(x) for x in ((class_preset or {}).get("braceletStats") or (class_preset or {}).get("bracelet_stats") or [])]
    role_specials = preset_specials or ROLE_SPECIALS[role]
    if category == "special" and any(key in text for key in role_specials):
        return "core"
    if category == "combatStat" and any(re.search(rf"{stat}\s*[+＋]", text) for stat in (preset_stats or ["치명", "특화", "신속"])):
        return "core"
    if role == "support" and ("아군" in text or "낙인" in text):
        return "core"
    if role == "dealer" and ("적에게 주는 피해" in text or "피해 증가" in text or "무기 공격력" in text or "공격력" in text):
        return "core"
    if category == "basic":
        return "secondary"
    if category == "combatStat":
        return "conditional" if "신속" in text else "secondary"
    if category == "special":
        return "conditional"
    return "unmatched"


def _expected_count(dist: dict[str, float]) -> float:
    return sum(int(k) * float(v) for k, v in dist.items())


def _attempts_from_probability(prob: float | None) -> float | None:
    if not prob or prob <= 0:
        return None
    return 1.0 / prob


def _assigned_count_probability(grade: str, effect_count: int) -> float | None:
    counts = ((_official_table().get("effectCounts") or {}).get(grade) or {}).get("assigned") or {}
    if not counts:
        return None
    eligible = [float(prob) for count, prob in counts.items() if int(count) >= int(effect_count)]
    return sum(eligible) if eligible else 0.0


def _category_probability_sequence(categories: list[str]) -> float | None:
    category_probs = _official_table().get("categoryProbabilities") or {}
    targets = [c for c in categories if c in category_probs]
    if not targets:
        return None
    excluded_by_category: dict[str, int] = {}
    probability = 1.0
    for category in targets:
        row = category_probs[category]
        display_prob = float(row.get("probability") or 0.0)
        max_count = int(row.get("maxCount") or 99)
        already = excluded_by_category.get(category, 0)
        if already >= max_count:
            return 0.0
        # 공식은 같은 효과 중복 제외를 공개합니다. v53은 카테고리 단위 매칭 단계라
        # 동일 카테고리의 최대 개수 제한만 보수적으로 반영하고, 옵션 개별 표기확률은 추정하지 않습니다.
        probability *= display_prob
        excluded_by_category[category] = already + 1
    return probability


def build_official_bracelet_t4_summary(character: CharacterSummary, class_preset: dict[str, Any] | None = None) -> dict[str, Any]:
    table = _official_table()
    item = next((x for x in character.accessories if x.slot == "팔찌"), None)
    role = _role_key(character, class_preset)
    grade = _bracelet_grade(item)
    effects = [str(x).strip() for x in ((item.bracelet_effects if item else []) or []) if str(x).strip()]
    category_rows = table.get("categoryProbabilities") or {}
    effect_counts = (table.get("effectCounts") or {}).get(grade) or {}
    leap = (table.get("leapPoints") or {}).get(grade) or {}
    matched = []
    unmatched = []
    for index, effect in enumerate(effects):
        category = _category_key(effect)
        official = _official_name(effect, category)
        role_match = _match_role(effect, category, role, class_preset)
        if category == "unknown":
            unmatched.append({"index": index, "rawEffect": effect, "reason": "category_unmatched"})
            continue
        cat_row = category_rows.get(category) or {}
        matched.append({
            "index": index,
            "rawEffect": effect,
            "officialName": official,
            "category": category,
            "categoryLabel": cat_row.get("label"),
            "categoryDisplayProbability": cat_row.get("probability"),
            "categoryMaxCount": cat_row.get("maxCount"),
            "value": _extract_number(effect),
            "matchRole": role_match,
            "isCore": role_match == "core",
            "isSecondary": role_match == "secondary",
            "isConditional": role_match == "conditional",
            "probabilityBasis": "official_category_probability",
        })
    target = [row for row in matched if row["matchRole"] in {"core", "secondary", "conditional"}]
    core = [row for row in matched if row["matchRole"] == "core"]
    target_categories = [row["category"] for row in (core or target)]
    category_sequence_probability = _category_probability_sequence(target_categories)
    assigned_count_prob = _assigned_count_probability(grade, len(target_categories)) if target_categories else None
    combined_probability = None
    if category_sequence_probability is not None and assigned_count_prob is not None:
        combined_probability = category_sequence_probability * assigned_count_prob
    return {
        "version": "v53-official-bracelet-t4-category-matching",
        "role": role,
        "source": (table.get("metadata") or {}).get("sourceUrl"),
        "grade": grade,
        "gradeLabel": (leap.get("label") or ("유물" if grade == "relic" else "고대")),
        "leapPoints": leap.get("points"),
        "effectCountRules": effect_counts,
        "expectedFixedEffectCount": _expected_count(effect_counts.get("fixed") or {}),
        "expectedAssignedEffectCount": _expected_count(effect_counts.get("assigned") or {}),
        "categoryProbabilities": category_rows,
        "duplicateRule": table.get("duplicateRule") or {},
        "matchedEffects": matched,
        "unmatchedEffects": unmatched,
        "targetEffects": core or target,
        "matchedEffectCount": len(matched),
        "unmatchedEffectCount": len(unmatched),
        "coreEffectCount": len(core),
        "targetCategorySequenceProbability": category_sequence_probability,
        "assignedCountProbability": assigned_count_prob,
        "combinedCategoryProbability": combined_probability,
        "expectedAttemptsCategoryBasis": _attempts_from_probability(combined_probability),
        "warning": None if matched else "현재 팔찌 효과를 공식 T4 카테고리와 매칭하지 못했습니다.",
        "limits": [
            "v53은 공식 팔찌 T4의 효과 개수/카테고리 확률을 현재 효과에 연결하는 단계입니다.",
            "옵션 개별 수치 구간별 표기확률은 공식 JSON에 아직 분리되지 않아 카테고리 기준 확률로만 표시합니다.",
        ],
        "formula": "카테고리 기준 조합 확률 = P(부여 효과 개수 충분) × 현재 핵심/유효 효과 카테고리 표기확률의 곱",
    }
