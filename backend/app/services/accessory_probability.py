from __future__ import annotations

import itertools
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.models.schemas import CharacterSummary, EquipmentItem


SUPPORT_CLASSES = {"바드", "도화가", "홀리나이트"}
GRADE_ORDER = {"하": 1, "중": 2, "상": 3}


def _config_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "config"
    if path.exists():
        return path
    return Path("/app/backend/config")


@lru_cache(maxsize=1)
def _official_table() -> dict[str, Any]:
    path = _config_dir() / "accessory_effect_probabilities_official.json"
    if not path.exists():
        path = _config_dir() / "accessory_polishing_probabilities_official.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _grade_probabilities() -> dict[str, float]:
    raw = (_official_table().get("gradeProbabilities") or {})
    if "상" in raw:
        return {"하": float(raw.get("하", 0.063)), "중": float(raw.get("중", 0.03)), "상": float(raw.get("상", 0.007))}
    return {
        "하": float((raw.get("low") or {}).get("probability", 0.063)),
        "중": float((raw.get("mid") or {}).get("probability", 0.03)),
        "상": float((raw.get("high") or {}).get("probability", 0.007)),
    }


def _role_key(character: CharacterSummary, class_preset: dict[str, Any] | None = None) -> str:
    role = str((class_preset or {}).get("role") or "")
    if role in {"support", "서포터"}:
        return "support"
    if str(character.class_name or "") in SUPPORT_CLASSES:
        return "support"
    return "dealer"


def _part_key(slot: str | None) -> str | None:
    text = str(slot or "")
    if "목걸이" in text:
        return "necklace"
    if "귀걸이" in text:
        return "earring"
    if "반지" in text:
        return "ring"
    return None


def _first_number(text: str) -> float | None:
    m = re.search(r"[+＋-]?(\d+(?:\.\d+)?)", str(text or ""))
    return float(m.group(1)) if m else None


def _grade_from_thresholds(value: float | None, thresholds: list[tuple[float, str]]) -> str:
    if value is None:
        return "하"
    for minimum, grade in thresholds:
        if value >= minimum:
            return grade
    return "하"


ACCESSORY_OPTION_DEFS: dict[str, list[dict[str, Any]]] = {
    "necklace": [
        {"name": "추가 피해", "keywords": ["추가 피해"], "roles": ["dealer"], "thresholds": [(2.6, "상"), (1.6, "중"), (0.0, "하")]},
        {"name": "적에게 주는 피해", "keywords": ["적에게 주는 피해"], "roles": ["dealer"], "thresholds": [(2.0, "상"), (1.2, "중"), (0.0, "하")]},
        {"name": "세레나데/신앙/조화 게이지 획득량", "keywords": ["세레나데", "신앙", "조화 게이지"], "roles": ["support"], "thresholds": [(8.0, "상"), (5.0, "중"), (0.0, "하")]},
        {"name": "낙인력", "keywords": ["낙인력"], "roles": ["support"], "thresholds": [(8.0, "상"), (5.0, "중"), (0.0, "하")]},
        {"name": "최대 생명력", "keywords": ["최대 생명력"], "roles": ["secondary"], "thresholds": [(1.0, "하")]},
        {"name": "최대 마나", "keywords": ["최대 마나"], "roles": ["secondary"], "thresholds": [(1.0, "하")]},
    ],
    "earring": [
        {"name": "무기 공격력 %", "keywords": ["무기 공격력"], "requiresPercent": True, "roles": ["dealer"], "thresholds": [(3.0, "상"), (1.8, "중"), (0.0, "하")]},
        {"name": "공격력 %", "keywords": ["공격력"], "requiresPercent": True, "roles": ["dealer"], "thresholds": [(1.55, "상"), (0.95, "중"), (0.0, "하")]},
        {"name": "파티원 회복 효과", "keywords": ["파티원 회복", "회복 효과"], "roles": ["support"], "thresholds": [(3.0, "상"), (1.5, "중"), (0.0, "하")]},
        {"name": "파티원 보호막 효과", "keywords": ["파티원 보호막", "보호막 효과"], "roles": ["support"], "thresholds": [(3.0, "상"), (1.5, "중"), (0.0, "하")]},
        {"name": "최대 생명력", "keywords": ["최대 생명력"], "roles": ["secondary"], "thresholds": [(1.0, "하")]},
        {"name": "최대 마나", "keywords": ["최대 마나"], "roles": ["secondary"], "thresholds": [(1.0, "하")]},
    ],
    "ring": [
        {"name": "치명타 적중률", "keywords": ["치명타 적중률"], "roles": ["dealer"], "thresholds": [(1.55, "상"), (0.95, "중"), (0.4, "하")]},
        {"name": "치명타 피해", "keywords": ["치명타 피해"], "roles": ["dealer"], "thresholds": [(4.0, "상"), (2.4, "중"), (1.1, "하")]},
        {"name": "아군 공격력 강화 효과", "keywords": ["아군 공격력 강화"], "roles": ["support"], "thresholds": [(5.0, "상"), (3.0, "중"), (1.35, "하")]},
        {"name": "아군 피해량 강화 효과", "keywords": ["아군 피해량 강화"], "roles": ["support"], "thresholds": [(7.5, "상"), (4.5, "중"), (2.0, "하")]},
        {"name": "최대 생명력", "keywords": ["최대 생명력"], "roles": ["secondary"], "thresholds": [(1.0, "하")]},
        {"name": "최대 마나", "keywords": ["최대 마나"], "roles": ["secondary"], "thresholds": [(1.0, "하")]},
    ],
}


def _definition_matches(effect: str, definition: dict[str, Any]) -> bool:
    text = str(effect or "")
    if definition.get("requiresPercent") and "%" not in text:
        return False
    if definition["name"] == "공격력 %" and "무기 공격력" in text:
        return False
    return any(keyword and keyword in text for keyword in definition.get("keywords", []))


def _match_effect(effect: str, part: str, role: str) -> dict[str, Any] | None:
    value = _first_number(effect)
    for definition in ACCESSORY_OPTION_DEFS.get(part, []):
        if not _definition_matches(effect, definition):
            continue
        grade = _grade_from_thresholds(value, definition.get("thresholds", []))
        roles = definition.get("roles", [])
        is_core = role in roles
        is_secondary = "secondary" in roles
        probability = _grade_probabilities().get(grade, 0.0)
        return {
            "rawEffect": effect,
            "officialName": definition["name"],
            "grade": grade,
            "gradeRank": GRADE_ORDER.get(grade, 1),
            "value": value,
            "displayProbability": probability,
            "isCore": is_core,
            "isSecondary": is_secondary,
            "matchRole": role if is_core else "secondary" if is_secondary else "nonCore",
        }
    return None


def _combination_probability(effects: list[dict[str, Any]]) -> float | None:
    probs = [float(row.get("displayProbability") or 0.0) for row in effects if float(row.get("displayProbability") or 0.0) > 0]
    if not probs:
        return None
    if len(probs) == 1:
        return probs[0]
    if len(probs) > 6:
        probs = probs[:6]
    total = 0.0
    for ordered in itertools.permutations(probs):
        excluded = 0.0
        p = 1.0
        valid = True
        for display_prob in ordered:
            denom = 1.0 - excluded
            if denom <= 0:
                valid = False
                break
            p *= display_prob / denom
            excluded += display_prob
        if valid:
            total += p
    return total


def _analyze_accessory(item: EquipmentItem, role: str) -> dict[str, Any]:
    part = _part_key(item.slot)
    effects = [str(x).strip() for x in (item.accessory_effects or []) if str(x).strip()]
    matched: list[dict[str, Any]] = []
    unmatched: list[str] = []
    if not part:
        return {
            "slot": item.slot,
            "name": item.name,
            "part": None,
            "matchedEffects": [],
            "unmatchedEffects": effects,
            "targetEffects": [],
            "combinationProbability": None,
            "expectedAttempts": None,
            "targetBasis": "unsupported_part",
            "warning": "지원하지 않는 장신구 부위입니다.",
        }
    for effect in effects:
        row = _match_effect(effect, part, role)
        if row:
            matched.append(row)
        else:
            unmatched.append(effect)

    core = [row for row in matched if row.get("isCore")]
    secondary = [row for row in matched if row.get("isSecondary")]
    if core:
        target = core
        basis = "core"
    elif secondary:
        target = secondary
        basis = "secondary"
    else:
        target = matched
        basis = "matched_non_core" if matched else "none"
    probability = _combination_probability(target)
    expected = None if not probability or probability <= 0 else 1.0 / probability
    return {
        "slot": item.slot,
        "name": item.name,
        "part": part,
        "role": role,
        "matchedEffects": matched,
        "unmatchedEffects": unmatched,
        "targetEffects": target,
        "targetBasis": basis,
        "combinationProbability": probability,
        "expectedAttempts": expected,
        "matchedCount": len(matched),
        "unmatchedCount": len(unmatched),
        "warning": None if matched else "공식 확률표와 매칭된 장신구 효과가 없습니다.",
    }


def build_official_accessory_effect_summary(character: CharacterSummary, class_preset: dict[str, Any] | None = None) -> dict[str, Any]:
    role = _role_key(character, class_preset)
    items = [
        _analyze_accessory(item, role)
        for item in character.accessories
        if item.slot != "팔찌"
    ]
    with_expected = [row for row in items if row.get("expectedAttempts")]
    most_difficult = max(with_expected, key=lambda row: float(row.get("expectedAttempts") or 0.0), default=None)
    matched_count = sum(int(row.get("matchedCount") or 0) for row in items)
    unmatched_count = sum(int(row.get("unmatchedCount") or 0) for row in items)
    return {
        "version": "v60.4-accessory-grade-thresholds",
        "role": role,
        "source": (_official_table().get("metadata") or {}).get("sourceUrl"),
        "duplicateRule": (_official_table().get("duplicateRule") or {}),
        "gradeProbabilities": _grade_probabilities(),
        "items": items,
        "matchedEffectCount": matched_count,
        "unmatchedEffectCount": unmatched_count,
        "mostDifficultItem": most_difficult,
        "formula": "순서 미상 조합 확률은 가능한 부여 순서별 조건부 확률을 합산합니다. 조건부 확률 = 표기확률 / (1 - 이미 제외된 표기확률 합).",
        "warning": None if matched_count else "현재 장신구 효과를 공식 확률표와 매칭하지 못했습니다.",
    }
