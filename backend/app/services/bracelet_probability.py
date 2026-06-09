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


def _safe_int(value: Any, allowed: set[int] | None = None) -> int | None:
    if value in (None, "", "unknown", "모름", "auto"):
        return None
    try:
        parsed = int(value)
    except Exception:
        return None
    if allowed is not None and parsed not in allowed:
        return None
    return parsed


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


def _category_probability_sum(categories: list[str]) -> float | None:
    category_probs = _official_table().get("categoryProbabilities") or {}
    unique = []
    for category in categories:
        if category in category_probs and category not in unique:
            unique.append(category)
    if not unique:
        return None
    return sum(float(category_probs[category].get("probability") or 0.0) for category in unique)


def _weighted_at_least_one_by_assigned_count(base_prob: float | None, assigned_dist: dict[str, float]) -> tuple[float | None, dict[str, float]]:
    if base_prob is None or base_prob <= 0 or not assigned_dist:
        return None, {}
    by_count: dict[str, float] = {}
    total = 0.0
    for count_text, count_prob in assigned_dist.items():
        count = int(count_text)
        p = 1.0 - ((1.0 - base_prob) ** count)
        by_count[count_text] = p
        total += float(count_prob) * p
    return total, by_count


def _infer_bracelet_counts(
    total_effect_count: int,
    special_effect_count: int,
    fixed_dist: dict[str, float],
    assigned_dist: dict[str, float],
    explicit_fixed: int | None,
    explicit_random: int | None,
) -> dict[str, Any]:
    allowed_fixed = sorted(int(k) for k in fixed_dist.keys())
    allowed_random = sorted(int(k) for k in assigned_dist.keys())
    possible_pairs = [(fixed, random) for fixed in allowed_fixed for random in allowed_random if fixed + random == total_effect_count]

    fixed = explicit_fixed
    random = explicit_random
    basis = "user_input" if fixed is not None and random is not None else "auto_estimate"
    reason = "사용자 입력"
    note = "사용자가 입력한 고정/랜덤 슬롯 수를 우선 적용했습니다."

    if basis != "user_input":
        reason = "총 옵션 수 기반 자동 추정"
        note = "현재 팔찌 총 효과 수와 공식 가능한 조합으로 자동 추정했습니다. 기본은 고정 2개 우선이며, 총 옵션 3개는 고정 1개/랜덤 2개로 보정합니다. 특수옵션이 3개면 랜덤 3개 구성을 우선합니다."

    if fixed is not None and random is None:
        candidate_random = total_effect_count - fixed
        random = candidate_random if candidate_random in allowed_random else None
        basis = "partial_user_input_auto_completed" if random is not None else "partial_user_input_incomplete"
        reason = "고정 수동 입력 + 랜덤 자동 보정"
    elif random is not None and fixed is None:
        candidate_fixed = total_effect_count - random
        fixed = candidate_fixed if candidate_fixed in allowed_fixed else None
        basis = "partial_user_input_auto_completed" if fixed is not None else "partial_user_input_incomplete"
        reason = "랜덤 수동 입력 + 고정 자동 보정"
    elif fixed is None and random is None:
        preferred = None
        special_pair = (total_effect_count - 3, 3)
        if special_effect_count >= 3 and special_pair in possible_pairs:
            preferred = special_pair
            basis = "auto_special_count"
            reason = "특수옵션 3개 감지"
            note = "특수옵션이 3개 감지되어 랜덤 부여효과 3개 구성으로 우선 추정했습니다."
        elif total_effect_count == 3 and (1, 2) in possible_pairs:
            preferred = (1, 2)
            reason = "총 옵션 3개 보정"
        else:
            with_two_fixed = [pair for pair in possible_pairs if pair[0] == 2]
            if with_two_fixed:
                preferred = max(with_two_fixed, key=lambda pair: pair[1])
            elif possible_pairs:
                preferred = max(possible_pairs, key=lambda pair: (pair[0], pair[1]))
        if preferred:
            fixed, random = preferred

    is_valid = fixed is not None and random is not None and fixed + random == total_effect_count
    if not is_valid and possible_pairs:
        fallback = possible_pairs[0]
        fixed, random = fallback
        basis = "auto_fallback"
        reason = "공식 가능한 조합 fallback"
        note = "입력값이 공식 가능한 조합과 맞지 않아 가능한 조합 중 하나로 보정했습니다."
        is_valid = True

    return {
        "totalEffectCount": total_effect_count,
        "specialEffectCount": special_effect_count,
        "fixedOptionCount": fixed,
        "randomOptionSlotCount": random,
        "basis": basis,
        "reason": reason,
        "isOfficiallyPossible": is_valid,
        "possiblePairs": [{"fixed": f, "random": r} for f, r in possible_pairs],
        "note": note,
    }


def _user_bracelet_input(
    memory_hints: dict[str, Any] | None,
    fixed_dist: dict[str, float],
    assigned_dist: dict[str, float],
    total_effect_count: int,
    special_effect_count: int,
) -> dict[str, Any]:
    bracelet = (memory_hints or {}).get("braceletAcquisition") or {}
    allowed_fixed = {int(k) for k in fixed_dist.keys()}
    allowed_random = {int(k) for k in assigned_dist.keys()}
    explicit_fixed = _safe_int(bracelet.get("fixedOptionCount"), allowed_fixed)
    explicit_random = _safe_int(bracelet.get("randomOptionSlotCount"), allowed_random)
    inference = _infer_bracelet_counts(total_effect_count, special_effect_count, fixed_dist, assigned_dist, explicit_fixed, explicit_random)
    return {
        "mode": bracelet.get("mode") or "unknown",
        "attempts": bracelet.get("attempts"),
        "explicitFixedOptionCount": explicit_fixed,
        "explicitRandomOptionSlotCount": explicit_random,
        "fixedOptionCount": inference["fixedOptionCount"],
        "randomOptionSlotCount": inference["randomOptionSlotCount"],
        "fixedCountBasis": "user_input" if explicit_fixed is not None else inference["basis"],
        "randomCountBasis": "user_input" if explicit_random is not None else inference["basis"],
        "hasExplicitFixedOptionCount": explicit_fixed is not None,
        "hasExplicitRandomOptionSlotCount": explicit_random is not None,
        "inference": inference,
    }


def build_official_bracelet_t4_summary(
    character: CharacterSummary,
    class_preset: dict[str, Any] | None = None,
    memory_hints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    table = _official_table()
    item = next((x for x in character.accessories if x.slot == "팔찌"), None)
    role = _role_key(character, class_preset)
    grade = _bracelet_grade(item)
    effects = [str(x).strip() for x in ((item.bracelet_effects if item else []) or []) if str(x).strip()]
    category_rows = table.get("categoryProbabilities") or {}
    effect_counts = (table.get("effectCounts") or {}).get(grade) or {}
    fixed_dist = effect_counts.get("fixed") or {}
    assigned_dist = effect_counts.get("assigned") or {}
    special_effect_count = sum(1 for effect in effects if _category_key(effect) == "special")
    user_input = _user_bracelet_input(memory_hints, fixed_dist, assigned_dist, len(effects), special_effect_count)
    random_slot_dist = {str(user_input["randomOptionSlotCount"]): 1.0} if user_input["randomOptionSlotCount"] is not None else assigned_dist
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
            "ownershipBasis": "visible_current_effect_mixed_fixed_and_random",
        })
    target = [row for row in matched if row["matchRole"] in {"core", "secondary", "conditional"}]
    core = [row for row in matched if row["matchRole"] == "core"]
    target_categories = [row["category"] for row in (core or target)]
    per_random_slot_category_probability = _category_probability_sum(target_categories)
    random_option_success_probability, by_assigned_count = _weighted_at_least_one_by_assigned_count(
        per_random_slot_category_probability,
        random_slot_dist,
    )
    fixed_effect_basis = {
        "officialDistribution": fixed_dist,
        "userFixedOptionCount": user_input["explicitFixedOptionCount"],
        "effectiveFixedOptionCount": user_input["fixedOptionCount"],
        "basis": user_input["fixedCountBasis"],
        "note": "구매 당시 고정 옵션 수는 베이스 구조 설명용입니다. 구매 후 직접 돌린 운으로 보지 않습니다.",
    }
    random_effect_basis = {
        "officialDistribution": assigned_dist,
        "userRandomOptionSlotCount": user_input["explicitRandomOptionSlotCount"],
        "effectiveRandomOptionSlotCount": user_input["randomOptionSlotCount"],
        "usedDistribution": random_slot_dist,
        "basis": user_input["randomCountBasis"],
        "note": "랜덤 슬롯 수는 자동 추정값 또는 사용자가 명시한 값 기준으로 기대값을 계산합니다.",
    }
    return {
        "version": "v57-bracelet-auto-slot-estimate",
        "role": role,
        "source": (table.get("metadata") or {}).get("sourceUrl"),
        "grade": grade,
        "gradeLabel": (leap.get("label") or ("유물" if grade == "relic" else "고대")),
        "leapPoints": leap.get("points"),
        "effectCountRules": effect_counts,
        "fixedEffectCountDistribution": fixed_dist,
        "assignedEffectCountDistribution": assigned_dist,
        "expectedFixedEffectCount": float(user_input["fixedOptionCount"]) if user_input["fixedOptionCount"] is not None else _expected_count(fixed_dist),
        "expectedAssignedEffectCount": float(user_input["randomOptionSlotCount"]) if user_input["randomOptionSlotCount"] is not None else _expected_count(assigned_dist),
        "categoryProbabilities": category_rows,
        "duplicateRule": table.get("duplicateRule") or {},
        "purchaseStructure": {
            "baseBraceletHasFixedOptions": True,
            "baseBraceletHasRandomOptionSlots": True,
            "bindsToRosterAfterPurchase": True,
            "fixedOptionsAreNotUserRngAfterPurchase": True,
            "onlyRandomOptionRerollsShouldBeComparedWithUserAttempts": True,
            "autoEstimateRule": "총 옵션 3개는 고정 1/랜덤 2, 총 옵션 4개는 기본 고정 2/랜덤 2, 총 옵션 5개는 고정 2/랜덤 3으로 우선 추정합니다. 단 특수옵션이 3개면 랜덤 3개 구성으로 우선 추정합니다. 수동 입력이 있으면 수동 입력을 우선합니다.",
            "userInput": user_input,
            "fixedEffectBasis": fixed_effect_basis,
            "randomEffectBasis": random_effect_basis,
            "description": "팔찌는 구매 시 고정 옵션과 랜덤 옵션 슬롯이 섞여 있으며, 구매 후 계정 귀속됩니다. 따라서 현재 효과 전체를 한 번에 직접 뽑은 목표로 계산하지 않습니다.",
        },
        "matchedEffects": matched,
        "unmatchedEffects": unmatched,
        "targetEffects": core or target,
        "matchedEffectCount": len(matched),
        "unmatchedEffectCount": len(unmatched),
        "coreEffectCount": len(core),
        "wholeBraceletEffectProbability": None,
        "wholeBraceletEffectExpectedAttempts": None,
        "wholeBraceletEffectReason": "현재 팔찌 효과에는 구매 당시 고정 옵션과 구매 후 직접 돌린 랜덤 옵션이 섞일 수 있어 전체 효과를 하나의 랜덤 목표로 계산하지 않습니다.",
        "randomOptionBasis": {
            "targetCategories": list(dict.fromkeys(target_categories)),
            "perRandomSlotCategoryProbability": per_random_slot_category_probability,
            "successProbabilityByAssignedCount": by_assigned_count,
            "weightedSuccessProbability": random_option_success_probability,
            "expectedAttempts": _attempts_from_probability(random_option_success_probability),
            "slotCountBasis": random_effect_basis["basis"],
            "userRandomOptionSlotCount": user_input["explicitRandomOptionSlotCount"],
            "effectiveRandomOptionSlotCount": user_input["randomOptionSlotCount"],
            "usedSlotDistribution": random_slot_dist,
            "formula": "랜덤 옵션 기준 확률 = Σ P(랜덤 슬롯 수=n) × [1-(1-p)^n]. p는 핵심/유효 카테고리 중 하나가 한 슬롯에 붙을 카테고리 기준 확률입니다.",
            "interpretation": "사용자가 팔찌를 직접 돌린 시도 수를 입력했을 때 비교할 기준입니다. 구매 당시 이미 붙어 있던 고정 옵션은 억까 판정 대상으로 보지 않습니다.",
        },
        "targetCategorySequenceProbability": None,
        "assignedCountProbability": random_option_success_probability,
        "combinedCategoryProbability": random_option_success_probability,
        "expectedAttemptsCategoryBasis": _attempts_from_probability(random_option_success_probability),
        "warning": None if matched else "현재 팔찌 효과를 공식 T4 카테고리와 매칭하지 못했습니다.",
        "limits": [
            "v57부터 팔찌 슬롯 수는 기본 자동 추정합니다. 수동 입력은 자동 추정보다 우선합니다.",
            "총 옵션 3개는 고정 1개/랜덤 2개로, 총 옵션 4개는 기본 고정 2개/랜덤 2개로, 총 옵션 5개는 고정 2개/랜덤 3개로 우선 추정합니다.",
            "특수옵션이 3개 감지되면 랜덤 3개 구성으로 우선 추정합니다.",
            "현재 팔찌 효과 전체를 하나의 랜덤 목표로 계산하지 않습니다.",
            "팔찌는 구매 시 고정 옵션과 랜덤 옵션 슬롯이 섞여 있으며, 구매 후 계정 귀속됩니다.",
            "억까 판정에는 사용자가 직접 돌린 랜덤 옵션 시도 수만 기대값과 비교해야 합니다.",
            "옵션 개별 수치 구간별 표기확률은 공식 JSON에 아직 분리되지 않아 카테고리 기준 확률로 표시합니다.",
        ],
        "formula": "전체 효과 확률은 계산하지 않음. 자동 추정 또는 사용자가 명시한 랜덤 슬롯 수 기준으로 기대값만 계산합니다.",
    }
