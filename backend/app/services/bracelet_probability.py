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


def build_official_bracelet_t4_summary(character: CharacterSummary, class_preset: dict[str, Any] | None = None) -> dict[str, Any]:
    table = _official_table()
    item = next((x for x in character.accessories if x.slot == "팔찌"), None)
    role = _role_key(character, class_preset)
    grade = _bracelet_grade(item)
    effects = [str(x).strip() for x in ((item.bracelet_effects if item else []) or []) if str(x).strip()]
    category_rows = table.get("categoryProbabilities") or {}
    effect_counts = (table.get("effectCounts") or {}).get(grade) or {}
    fixed_dist = effect_counts.get("fixed") or {}
    assigned_dist = effect_counts.get("assigned") or {}
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
        assigned_dist,
    )
    return {
        "version": "v55-bracelet-fixed-random-split",
        "role": role,
        "source": (table.get("metadata") or {}).get("sourceUrl"),
        "grade": grade,
        "gradeLabel": (leap.get("label") or ("유물" if grade == "relic" else "고대")),
        "leapPoints": leap.get("points"),
        "effectCountRules": effect_counts,
        "fixedEffectCountDistribution": fixed_dist,
        "assignedEffectCountDistribution": assigned_dist,
        "expectedFixedEffectCount": _expected_count(fixed_dist),
        "expectedAssignedEffectCount": _expected_count(assigned_dist),
        "categoryProbabilities": category_rows,
        "duplicateRule": table.get("duplicateRule") or {},
        "purchaseStructure": {
            "baseBraceletHasFixedOptions": True,
            "baseBraceletHasRandomOptionSlots": True,
            "bindsToRosterAfterPurchase": True,
            "fixedOptionsAreNotUserRngAfterPurchase": True,
            "onlyRandomOptionRerollsShouldBeComparedWithUserAttempts": True,
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
            "formula": "랜덤 옵션 기준 확률 = Σ P(랜덤 슬롯 수=n) × [1-(1-p)^n]. p는 핵심/유효 카테고리 중 하나가 한 슬롯에 붙을 카테고리 기준 확률입니다.",
            "interpretation": "사용자가 팔찌를 직접 돌린 시도 수를 입력했을 때 비교할 기준입니다. 구매 당시 이미 붙어 있던 고정 옵션은 억까 판정 대상으로 보지 않습니다.",
        },
        # Backward-compatible fields for older frontend cards. They intentionally no longer mean
        # whole-bracelet probability and should be treated as random-option-basis values.
        "targetCategorySequenceProbability": None,
        "assignedCountProbability": random_option_success_probability,
        "combinedCategoryProbability": random_option_success_probability,
        "expectedAttemptsCategoryBasis": _attempts_from_probability(random_option_success_probability),
        "warning": None if matched else "현재 팔찌 효과를 공식 T4 카테고리와 매칭하지 못했습니다.",
        "limits": [
            "v55부터 현재 팔찌 효과 전체 5개를 하나의 랜덤 목표로 계산하지 않습니다.",
            "팔찌는 구매 시 고정 옵션과 랜덤 옵션 슬롯이 섞여 있으며, 구매 후 계정 귀속됩니다.",
            "억까 판정에는 사용자가 직접 돌린 랜덤 옵션 시도 수만 기대값과 비교해야 합니다.",
            "옵션 개별 수치 구간별 표기확률은 공식 JSON에 아직 분리되지 않아 카테고리 기준 확률로 표시합니다.",
        ],
        "formula": "전체 효과 확률은 계산하지 않음. 랜덤 옵션 슬롯 기준 기대값만 계산합니다.",
    }
