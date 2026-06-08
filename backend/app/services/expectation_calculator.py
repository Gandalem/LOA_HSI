from __future__ import annotations

from functools import lru_cache
from math import log
from pathlib import Path
from typing import Any
import json

from app.models.schemas import CharacterSummary



def _config_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "config"
    if path.exists():
        return path
    return Path("/app/backend/config")


@lru_cache(maxsize=1)
def _official_accessory_polishing_table() -> dict[str, Any]:
    path = _config_dir() / "accessory_polishing_probabilities_official.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _official_accessory_polishing_summary() -> dict[str, Any]:
    table = _official_accessory_polishing_table()
    parts = table.get("parts") or {}
    return {
        "metadata": table.get("metadata") or {},
        "gradeProbabilities": table.get("gradeProbabilities") or ACCESSORY_POLISHING_DISPLAY_PROBS,
        "partOptionCounts": {part: len(options) for part, options in parts.items()},
        "parts": parts,
        "loaded": bool(table),
    }

# 확률 페이지/커뮤니티 검증값을 런타임에 매번 조회하지 않기 위해 로컬 규칙으로 고정합니다.
# 공식 확률 페이지는 각 옵션별 10회 세공, 성공 횟수별 레벨 환산, 장신구 중복 제외, 팔찌 T4 효과 수/카테고리 확률을 공개합니다.
# 커뮤니티 글은 직업/역할별 유효 옵션 해석과 악세/팔찌 목표 조합 해석의 참고값으로 사용합니다.

STONE_ATTEMPTS_PER_OPTION = 10

# 공식표 기준: UI/API에 표시되는 1~4 값은 "세공 성공 횟수"가 아니라 "활성화 레벨"입니다.
# 성공 횟수 0~5회 = 0레벨, 6회 = 1레벨, 7~8회 = 2레벨, 9회 = 3레벨, 10회 = 4레벨.
ACTIVE_LEVEL_TO_MIN_SUCCESS = {0: 0, 1: 6, 2: 7, 3: 9, 4: 10}

# 9/7, 10/7, 9/9는 성공 횟수 기준으로 널리 쓰이는 검증값입니다.
# 활성화 레벨 기준으로는 9/7 = 3/2 이상, 10/7 = 4/2 이상, 9/9 = 3/3 이상입니다.
STONE_REFERENCE_TARGETS_BY_SUCCESS = {
    (9, 7): {"prob": 1.0 / 735.0, "expectedStones": 735.0, "source": "official_table_community_verified"},
    (10, 7): {"prob": 1.0 / 26142.0, "expectedStones": 26142.0, "source": "official_table_community_verified"},
    (9, 9): {"prob": 1.0 / 26142.0, "expectedStones": 26142.0, "source": "official_table_community_verified"},
}

# 장신구 연마 표기확률. 실제 연속 부여에서는 이미 부여된 효과가 제외되어 보정됩니다.
ACCESSORY_POLISHING_DISPLAY_PROBS = {
    "상": 0.007,   # 0.7000%
    "중": 0.030,   # 3.0000%
    "하": 0.063,   # 6.3000%
}

# 인벤 기대값 글 방식에 맞춰 “3연마 결과에서 유효 등급 조합을 얻는 확률”을 별도 지표로 둡니다.
# 이 값은 공식 표기확률+중복 제외 규칙 기반 근사값이며, 커뮤니티 계산과 비교하기 위한 표시용입니다.
ACCESSORY_COMBO_REFERENCE_PROBS = {
    "상상": 0.00030,       # 약 0.03%
    "상중 이상": 0.00280,  # 약 0.28%
    "상하 이상": 0.00620,
    "중중 이상": 0.02000,
    "중하 이상": 0.08300,
    "하하 이상": 0.29400,  # 커뮤니티 글의 하단일/하급권 해석과 비교용 보수값
}

# 역할별 유효 옵션 프리셋. 직업별 세부 빌드는 계속 바뀌므로 “수정 가능한 로컬 프리셋”으로 둡니다.
SUPPORT_CLASSES = {"바드", "도화가", "홀리나이트"}

CLASS_ALIASES = {
    "버서커": "dealer", "디스트로이어": "dealer", "워로드": "dealer", "홀리나이트": "support", "슬레이어": "dealer", "발키리": "dealer",
    "배틀마스터": "dealer", "인파이터": "dealer", "기공사": "dealer", "창술사": "dealer", "스트라이커": "dealer", "브레이커": "dealer",
    "데빌헌터": "dealer", "블래스터": "dealer", "호크아이": "dealer", "스카우터": "dealer", "건슬링어": "dealer",
    "바드": "support", "서머너": "dealer", "아르카나": "dealer", "소서리스": "dealer",
    "블레이드": "dealer", "데모닉": "dealer", "리퍼": "dealer", "소울이터": "dealer",
    "도화가": "support", "기상술사": "dealer", "환수사": "dealer", "가디언나이트": "dealer",
}

ACCESSORY_CORE_EFFECTS = {
    "dealer": ["추가 피해", "무기 공격력", "공격력", "치명타 피해", "치명타 적중률", "적에게 주는 피해"],
    "support": ["낙인력", "아군 피해량 강화", "아군 공격력 강화", "세레나데", "환영의 문"],
}

ACCESSORY_SECONDARY_EFFECTS = {
    "dealer": ["최대 생명력", "최대 마나"],
    "support": ["무기 공격력", "공격력", "최대 생명력"],
}

# Backward compatibility alias for older frontend keys.
ACCESSORY_VALID_EFFECTS = ACCESSORY_CORE_EFFECTS

BRACELET_SPECIAL_EFFECTS = [
    "쐐기", "망치", "순환", "정밀", "습격", "우월", "열정", "냉정", "상처악화", "기습", "결투", "강타", "마무리", "분개", "돌진", "멸시", "타격",
    "비수", "약점 노출", "응원", "깨달음", "앵콜", "긴급수혈", "마나회수", "응급처치", "투자", "반격", "보상",
]

BRACELET_VALID_EFFECTS = {
    "dealer": ["쐐기", "망치", "순환", "정밀", "습격", "우월", "열정", "냉정", "상처악화"],
    "support": ["비수", "약점 노출", "응원", "깨달음", "마나회수", "앵콜"],
}


BRACELET_TEXT_VALID_PATTERNS = {
    "dealer": [
        "적에게 주는 피해", "피해가", "피해 증가", "무기 공격력", "공격력 +", "치명 +", "특화 +", "신속 +", "방향성 공격이 아닌 스킬",
    ],
    "support": [
        "아군 공격력 강화", "아군 피해량 강화", "치명타 저항", "낙인", "비수", "약점 노출", "응원", "깨달음", "특화 +", "신속 +", "최대 마나", "마나회수",
    ],
}


def _bracelet_effect_buckets(effects: list[str], role: str, class_preset: dict[str, Any] | None = None) -> dict[str, list[str]]:
    preset_options, preset_stats = _preset_bracelet_keywords(class_preset)
    named = preset_options or BRACELET_VALID_EFFECTS[role]
    valid: list[str] = []
    secondary: list[str] = []
    conditional: list[str] = []
    non_core: list[str] = []
    for effect in effects:
        e = str(effect).strip()
        if not e:
            continue
        is_named = any(key in e for key in named)
        if role == "support":
            # 서포터 핵심: 파티 시너지/버프/특화 계열.
            # 단순 지능/힘/민첩은 조건부 발동이 아니라 보조 스탯으로 분리합니다.
            is_core = (
                is_named
                or "아군 공격력 강화" in e
                or "아군 피해량 강화" in e
                or "치명타 저항" in e
                or ("치명타 저항" in e and any(x in named for x in ["비수", "약점 노출"]))
                or ("아군 공격력 강화" in e and "응원" in named)
                or "낙인" in e
                or "특화 +" in e
                or any((stat + " +") in e for stat in preset_stats)
            )
            is_secondary = "지능 +" in e or "힘 +" in e or "민첩 +" in e or "체력 +" in e
            is_conditional = "신속 +" in e or "최대 마나" in e or "마나" in e
        else:
            # 딜러 핵심: 피해/공격력/주요 특성. 타대 문구와 쿨증피증은 조건부로 둡니다.
            is_core = (
                is_named
                or "적에게 주는 피해" in e
                or "피해 증가" in e
                or "무기 공격력" in e
                or "공격력 +" in e
                or "치명 +" in e
                or "특화 +" in e
                or any((stat + " +") in e for stat in preset_stats)
            )
            is_secondary = "힘 +" in e or "민첩 +" in e or "지능 +" in e or "체력 +" in e
            is_conditional = "신속 +" in e or "방향성 공격이 아닌 스킬" in e or "스킬 재사용 대기시간" in e
        if is_core:
            valid.append(e)
        elif is_secondary:
            secondary.append(e)
        elif is_conditional:
            conditional.append(e)
        else:
            non_core.append(e)
    return {
        "valid": valid,
        "secondary": secondary,
        "conditional": conditional,
        "nonCore": non_core,
        "validLike": valid + secondary + conditional,
    }

def _bracelet_valid_like_effects(effects: list[str], role: str, class_preset: dict[str, Any] | None = None) -> list[str]:
    return _bracelet_effect_buckets(effects, role, class_preset)["validLike"]

BRACELET_T4_RULES = {
    "유물": {
        "leap_points": 9,
        "fixed_count": {1: 0.65, 2: 0.35},
        "assigned_count": {1: 0.75, 2: 0.25},
    },
    "고대": {
        "leap_points": 18,
        "fixed_count": {1: 0.65, 2: 0.35},
        "assigned_count": {2: 0.75, 3: 0.25},
    },
}

BRACELET_CATEGORY_PROBS = {
    "기본 효과": 0.35,
    "전투 특성": 0.35,
    "특수 효과": 0.30,
}

P_TARGETS = {"50%": 0.50, "90%": 0.90, "99%": 0.99}


def _role_key_from_preset(class_preset: dict[str, Any] | None, fallback: str) -> str:
    role = str((class_preset or {}).get("role") or "")
    if "서포터" in role:
        return "support"
    if "딜러" in role:
        return "dealer"
    return fallback


def _flatten_polish_options_from_preset(class_preset: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    """Return (core, secondary) keyword lists for accessory polishing."""
    if not class_preset:
        return [], []
    opts = class_preset.get("polishOptions") or class_preset.get("polish_options") or {}
    role = str(class_preset.get("role") or "")
    core: list[str] = []
    secondary: list[str] = []
    if isinstance(opts, dict):
        if "서포터" in role:
            for key in ["party_damage"]:
                core.extend(str(x) for x in (opts.get(key) or []))
            for key in ["survival", "stats"]:
                secondary.extend(str(x) for x in (opts.get(key) or []))
        else:
            for value in opts.values():
                if isinstance(value, list):
                    core.extend(str(x) for x in value)
    def dedupe(values: list[str]) -> list[str]:
        out: list[str] = []
        for v in values:
            if v and v not in out:
                out.append(v)
        return out
    return dedupe(core), dedupe(secondary)


def _preset_bracelet_keywords(class_preset: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    if not class_preset:
        return [], []
    return [str(x) for x in (class_preset.get("braceletOptions") or class_preset.get("bracelet_options") or [])], [str(x) for x in (class_preset.get("braceletStats") or class_preset.get("bracelet_stats") or [])]


def _character_role(character: CharacterSummary) -> str:
    cls = character.class_name or ""
    return CLASS_ALIASES.get(cls, "support" if cls in SUPPORT_CLASSES else "dealer")


def _attempts_for_at_least_once(prob: float, target_probability: float) -> float | None:
    if prob <= 0 or prob >= 1:
        return None if prob <= 0 else 1.0
    return log(1.0 - target_probability) / log(1.0 - prob)


def _expected_from_count_dist(dist: dict[int, float]) -> float:
    return sum(k * v for k, v in dist.items())


def expected_attempts_from_probability(prob: float) -> float | None:
    if prob <= 0:
        return None
    return 1.0 / prob


# 보조 DP: 9/7 등 주요 검증값은 STONE_REFERENCE_TARGETS를 우선 사용합니다.
def _stone_strategy(rem1: int, rem2: int, rem_neg: int, pos1: int, pos2: int, rate_index: int) -> str:
    rate = rate_index / 100.0
    if rate >= 0.55 and (rem1 > 0 or rem2 > 0):
        return "pos1" if (rem1 >= rem2 and rem1 > 0) or rem2 == 0 else "pos2"
    if rate >= 0.45 and (rem1 > 0 or rem2 > 0):
        target = "pos1" if pos1 <= pos2 and rem1 > 0 else "pos2"
        if target == "pos2" and rem2 <= 0 and rem1 > 0:
            target = "pos1"
        return target
    if rem_neg > 0:
        return "neg"
    if rem1 > 0 or rem2 > 0:
        return "pos1" if rem1 >= rem2 and rem1 > 0 else "pos2"
    return "neg"


@lru_cache(maxsize=1)
def stone_result_distribution() -> dict[tuple[int, int, int], float]:
    @lru_cache(maxsize=None)
    def dp(rem1: int, rem2: int, rem_neg: int, pos1: int, pos2: int, neg: int, rate_idx: int):
        if rem1 + rem2 + rem_neg == 0:
            return {(pos1, pos2, neg): 1.0}
        target = _stone_strategy(rem1, rem2, rem_neg, pos1, pos2, rate_idx)
        p = rate_idx / 100.0
        succ_rate_idx = max(25, rate_idx - 10)
        fail_rate_idx = min(75, rate_idx + 10)
        if target == "pos1":
            succ_state = (rem1 - 1, rem2, rem_neg, pos1 + 1, pos2, neg, succ_rate_idx)
            fail_state = (rem1 - 1, rem2, rem_neg, pos1, pos2, neg, fail_rate_idx)
        elif target == "pos2":
            succ_state = (rem1, rem2 - 1, rem_neg, pos1, pos2 + 1, neg, succ_rate_idx)
            fail_state = (rem1, rem2 - 1, rem_neg, pos1, pos2, neg, fail_rate_idx)
        else:
            succ_state = (rem1, rem2, rem_neg - 1, pos1, pos2, neg + 1, succ_rate_idx)
            fail_state = (rem1, rem2, rem_neg - 1, pos1, pos2, neg, fail_rate_idx)
        out: dict[tuple[int, int, int], float] = {}
        for result, prob in dp(*succ_state).items():
            out[result] = out.get(result, 0.0) + prob * p
        for result, prob in dp(*fail_state).items():
            out[result] = out.get(result, 0.0) + prob * (1.0 - p)
        return out
    return dict(dp(10, 10, 10, 0, 0, 0, 75))


def _active_level_to_min_success(value: int) -> int:
    """Convert displayed activation level to minimum successful facets.

    Values 0~4 are activation levels. Values above 4 are treated as legacy success-count targets
    for backward compatibility with labels such as 9/7.
    """
    v = int(value)
    if v <= 4:
        return ACTIVE_LEVEL_TO_MIN_SUCCESS.get(v, 10)
    return v


def _success_count_to_active_level(success_count: int) -> int:
    s = int(success_count)
    if s >= 10:
        return 4
    if s >= 9:
        return 3
    if s >= 7:
        return 2
    if s >= 6:
        return 1
    return 0


def _normalize_stone_target(target_high: int, target_low: int) -> tuple[int, int, int, int]:
    """Return (activation_high, activation_low, success_high, success_low)."""
    high = int(target_high)
    low = int(target_low)
    if high <= 4 and low <= 4:
        active_high, active_low = high, low
        success_high = _active_level_to_min_success(active_high)
        success_low = _active_level_to_min_success(active_low)
    else:
        success_high, success_low = high, low
        active_high = _success_count_to_active_level(success_high)
        active_low = _success_count_to_active_level(success_low)
    if success_low > success_high:
        success_high, success_low = success_low, success_high
        active_high, active_low = active_low, active_high
    return active_high, active_low, success_high, success_low


@lru_cache(maxsize=128)
def stone_target_probability(target_high: int, target_low: int, max_negative: int | None = None) -> float:
    """Probability that one automatically faceted stone reaches the target.

    `target_high/target_low` is interpreted as activation levels when both values are 0~4.
    Example: displayed 3/1 means activation level 3 and 1, which corresponds to at least
    9 and 6 successful facets. Legacy success-count targets such as 9/7 still work.
    """
    _active_high, _active_low, success_high, success_low = _normalize_stone_target(target_high, target_low)
    key = (int(success_high), int(success_low))
    if max_negative is None and key in STONE_REFERENCE_TARGETS_BY_SUCCESS:
        return STONE_REFERENCE_TARGETS_BY_SUCCESS[key]["prob"]
    total = 0.0
    for (p1, p2, neg), prob in stone_result_distribution().items():
        high, low = sorted([p1, p2], reverse=True)
        if high >= success_high and low >= success_low:
            if max_negative is None or _success_count_to_active_level(neg) <= max_negative:
                total += prob
    return total


def _stone_target(character: CharacterSummary) -> tuple[int, int, int | None]:
    stone = character.ability_stone
    if not stone or stone.positive_1_points is None or stone.positive_2_points is None:
        return 7, 7, None
    high, low = sorted([int(stone.positive_1_points), int(stone.positive_2_points)], reverse=True)
    neg = int(stone.negative_points) if stone.negative_points is not None else None
    return high, low, neg


def _stone_expectation(character: CharacterSummary, stone_price_gold: float) -> dict[str, Any]:
    target_high, target_low, negative = _stone_target(character)
    active_high, active_low, success_high, success_low = _normalize_stone_target(target_high, target_low)
    prob = stone_target_probability(active_high, active_low, None)
    expected_stones = expected_attempts_from_probability(prob)
    # 공식/커뮤니티에서 흔히 말하는 9/7은 성공 횟수 기준이며, 활성 레벨 기준으로는 3/2 이상입니다.
    verification_prob = stone_target_probability(3, 2, None)
    verification_expected = expected_attempts_from_probability(verification_prob)
    return {
        "target": f"{active_high}/{active_low}",
        "targetKind": "activation_level",
        "successCountTarget": f"{success_high}/{success_low}",
        "negativePoints": negative,
        "successProbabilityPerStone": prob,
        "expectedStones": expected_stones,
        "expectedGold": None if expected_stones is None else expected_stones * stone_price_gold,
        "reference97Probability": verification_prob,
        "reference97ExpectedStones": verification_expected,
        "reference97ExpectedGold": None if verification_expected is None else verification_expected * stone_price_gold,
        "verified": 700 <= (verification_expected or 0) <= 770,
        "formula": "활성 레벨을 성공 횟수 기준으로 변환한 뒤, 기대 스톤 개수 = 1 / 목표 달성 확률로 계산합니다.",
        "model": "표시값 3/1은 성공 횟수 3/1이 아니라 활성 레벨 3/1입니다. 활성 3/1은 성공 횟수 9/6 이상으로 변환해 계산합니다.",
    }


def _accessory_combo_expectation(character: CharacterSummary, class_preset: dict[str, Any] | None = None) -> dict[str, Any]:
    role = _role_key_from_preset(class_preset, _character_role(character))
    preset_core, preset_secondary = _flatten_polish_options_from_preset(class_preset)
    core_effects = preset_core or ACCESSORY_CORE_EFFECTS[role]
    secondary_effects = preset_secondary or ACCESSORY_SECONDARY_EFFECTS[role]
    combos: dict[str, Any] = {}
    for name, prob in ACCESSORY_COMBO_REFERENCE_PROBS.items():
        combos[name] = {
            "probability": prob,
            "expectedAttempts": expected_attempts_from_probability(prob),
            "attemptsForAtLeastOnce": {label: _attempts_for_at_least_once(prob, q) for label, q in P_TARGETS.items()},
        }
    current_effects: list[str] = []
    for acc in character.accessories:
        if acc.slot == "팔찌":
            continue
        current_effects.extend(acc.accessory_effects or [])

    # Ignore aggregate rows that simply concatenate already-parsed effects, but preserve real duplicate
    # effect lines across multiple accessories. This lets the UI show both "3 core types" and
    # "5 core effect lines" for cases like two rings having the same support option.
    import re

    filtered_lines: list[str] = []
    for effect in current_effects:
        e = str(effect).strip()
        if not e:
            continue
        numbers = re.findall(r"[+＋-]?\d+(?:\.\d+)?\s*%?", e)
        looks_aggregate = len(numbers) >= 2 and any(short and short != e and short in e for short in current_effects)
        if looks_aggregate:
            continue
        filtered_lines.append(e)

    display_unique: list[str] = []
    for e in filtered_lines:
        if e not in display_unique:
            display_unique.append(e)

    def _first_matching_type(effect: str, presets: list[str]) -> str | None:
        return next((name for name in presets if name in effect), None)

    core_lines = [e for e in filtered_lines if _first_matching_type(e, core_effects)]
    secondary_lines = [e for e in filtered_lines if e not in core_lines and _first_matching_type(e, secondary_effects)]
    non_core_lines = [e for e in filtered_lines if e not in core_lines and e not in secondary_lines]

    core_types: list[str] = []
    for e in core_lines:
        t = _first_matching_type(e, core_effects)
        if t and t not in core_types:
            core_types.append(t)

    secondary_types: list[str] = []
    for e in secondary_lines:
        t = _first_matching_type(e, secondary_effects)
        if t and t not in secondary_types:
            secondary_types.append(t)

    core_display: list[str] = []
    for e in core_lines:
        if e not in core_display:
            core_display.append(e)

    secondary_display: list[str] = []
    for e in secondary_lines:
        if e not in secondary_display:
            secondary_display.append(e)

    non_core_display: list[str] = []
    for e in non_core_lines:
        if e not in non_core_display:
            non_core_display.append(e)

    return {
        "role": role,
        "classPreset": class_preset,
        "validEffects": core_effects,
        "coreEffectsPreset": core_effects,
        "secondaryEffectsPreset": secondary_effects,
        "currentParsedEffects": display_unique[:30],
        "currentParsedEffectCount": len(filtered_lines),
        "currentParsedUniqueEffectCount": len(display_unique),
        "currentValidLikeEffects": core_display[:30],
        "currentValidLikeCount": len(core_types),
        "currentCoreEffects": core_display[:30],
        "currentCoreCount": len(core_types),
        "currentCoreTypeCount": len(core_types),
        "currentCoreTypes": core_types[:30],
        "currentCoreEffectLineCount": len(core_lines),
        "currentSecondaryEffects": secondary_display[:30],
        "currentSecondaryCount": len(secondary_types),
        "currentSecondaryTypeCount": len(secondary_types),
        "currentSecondaryTypes": secondary_types[:30],
        "currentSecondaryEffectLineCount": len(secondary_lines),
        "currentNonCoreEffects": non_core_display[:30],
        "currentNonCoreCount": len(non_core_lines),
        "comboTargets": combos,
        "formula": "n회 안에 1번 이상 성공할 확률 = 1 - (1 - p)^n, 목표 확률 q까지 필요한 횟수 = log(1-q) / log(1-p)",
        "rule": "상/중/하 옵션 중복 제외 규칙을 반영한 조합 확률 기준입니다. 직업별 유효 옵션은 핵심/보조/비핵심 프리셋으로 분리합니다.",
    }

def _bracelet_target_expectation(character: CharacterSummary, class_preset: dict[str, Any] | None = None) -> dict[str, Any]:
    role = _role_key_from_preset(class_preset, _character_role(character))
    bracelet = next((x for x in character.accessories if x.slot == "팔찌"), None)
    grade = bracelet.grade if bracelet and bracelet.grade in BRACELET_T4_RULES else "고대"
    rule = BRACELET_T4_RULES[grade]
    preset_options, _preset_stats = _preset_bracelet_keywords(class_preset)
    valid_specials = preset_options or BRACELET_VALID_EFFECTS[role]
    p_valid_special_given_special = len(valid_specials) / max(1, len(BRACELET_SPECIAL_EFFECTS))
    p_valid_per_effect = BRACELET_CATEGORY_PROBS["특수 효과"] * p_valid_special_given_special

    by_assigned_count = {}
    target_prob = 0.0
    for count, count_prob in rule["assigned_count"].items():
        p = 1.0 - ((1.0 - p_valid_per_effect) ** count)
        by_assigned_count[count] = p
        target_prob += count_prob * p

    expected_attempts = expected_attempts_from_probability(target_prob)
    effects = bracelet.bracelet_effects if bracelet else []
    buckets = _bracelet_effect_buckets(effects, role, class_preset)
    current_valid = buckets["validLike"]
    return {
        "role": role,
        "classPreset": class_preset,
        "grade": grade,
        "leapPoints": rule["leap_points"],
        "expectedFixedEffectCount": _expected_from_count_dist(rule["fixed_count"]),
        "expectedAssignedEffectCount": _expected_from_count_dist(rule["assigned_count"]),
        "categoryProbability": BRACELET_CATEGORY_PROBS,
        "validSpecialEffects": valid_specials,
        "targetProbabilityOneOrMoreValidSpecial": target_prob,
        "expectedAttemptsForValidSpecial": expected_attempts,
        "attemptsForAtLeastOnce": {label: _attempts_for_at_least_once(target_prob, q) for label, q in P_TARGETS.items()},
        "byAssignedCount": by_assigned_count,
        "currentParsedEffectCount": len(effects),
        "currentParsedSpecialLikeCount": len(current_valid),
        "currentValidLikeEffects": current_valid,
        "currentValidEffects": buckets["valid"],
        "currentSecondaryEffects": buckets["secondary"],
        "currentConditionalEffects": buckets["conditional"],
        "currentNonCoreEffects": buckets["nonCore"],
        "formula": "유효 특수효과 1개 이상 확률 = Σ P(부여효과 개수=n) × [1-(1-p)^n]",
        "rule": "직업/역할별 유효 특수효과 목록은 로컬 프리셋으로 관리하며, 조회 시 외부 페이지를 다시 요청하지 않습니다.",
    }


def _accessory_single_slot() -> dict[str, Any]:
    return {
        label: {
            "displayProbability": prob,
            "expectedAttempts": expected_attempts_from_probability(prob),
        }
        for label, prob in ACCESSORY_POLISHING_DISPLAY_PROBS.items()
    }


def build_expected_value_summary(character: CharacterSummary, stone_price_gold: float = 5000.0, class_preset: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "abilityStone": _stone_expectation(character, stone_price_gold),
        "accessoryPolishing": {
            "single_slot": _accessory_single_slot(),
            "combination": _accessory_combo_expectation(character, class_preset),
            "officialProbabilityTable": _official_accessory_polishing_summary(),
            "duplicateRule": "이미 부여된 효과가 제외되면 실제 확률 = 표기확률 / (100% - 제외된 효과 표기확률 합)으로 보정합니다.",
            "scoreRule": "v43에서는 장신구 획득 방식/직접 연마 시도 수 입력을 아직 받지 않으므로 억까 지수에는 반영하지 않고 공식 확률표만 로컬 데이터로 보관합니다.",
        },
        "braceletT4": _bracelet_target_expectation(character, class_preset),
        "classEngravingPreset": class_preset,
        "presetVersion": "v43-official-accessory-probabilities",
    }
