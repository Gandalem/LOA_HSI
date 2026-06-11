from __future__ import annotations

from typing import Any

from app.models.schemas import CharacterSummary, EquipmentItem


def _n(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _i(value: Any) -> int | None:
    try:
        if value in (None, "", "unknown", "모름"):
            return None
        parsed = int(float(value))
        return parsed if parsed >= 0 else None
    except Exception:
        return None


def _gold(value: float | None) -> float | None:
    if value is None:
        return None
    if value >= 10000:
        return float(round(value / 1000) * 1000)
    if value >= 1000:
        return float(round(value / 100) * 100)
    return float(round(value))


def _part(slot: str | None) -> str:
    text = str(slot or "")
    if "목걸이" in text:
        return "necklace"
    if "귀걸이" in text:
        return "earring"
    if "반지" in text:
        return "ring"
    return "accessory"


def _part_label(part: str) -> str:
    return {"necklace": "목걸이", "earring": "귀걸이", "ring": "반지"}.get(part, "장신구")


def _quality_band(q: int | None) -> str:
    if q is None:
        return "품질 미상"
    if q >= 95:
        return "95+"
    if q >= 90:
        return "90-94"
    if q >= 80:
        return "80-89"
    if q >= 70:
        return "70-79"
    return "70 미만"


def _quality_mult(q: int | None) -> float:
    if q is None:
        return 1.0
    if q >= 80:
        return min(2.2, 1.0 + (q - 80) * 0.018)
    return max(0.55, 1.0 - (80 - q) * 0.006)


def _accessory_item(item: EquipmentItem, official: dict[str, Any] | None) -> dict[str, Any]:
    part = str((official or {}).get("part") or _part(item.slot))
    base = {"necklace": 180000.0, "earring": 90000.0, "ring": 85000.0}.get(part, 70000.0)
    targets = (official or {}).get("targetEffects") or []
    matched = (official or {}).get("matchedEffects") or []
    core = sum(1 for row in targets if row.get("isCore"))
    secondary = sum(1 for row in targets if row.get("isSecondary"))
    high = sum(1 for row in targets if int(row.get("gradeRank") or 0) >= 3)
    mid = sum(1 for row in targets if int(row.get("gradeRank") or 0) == 2)
    mult = 1.0 + core * 1.65 + secondary * 0.45 + high * 0.55 + mid * 0.20
    if not targets and not matched:
        mult *= 0.75
    median = base * _quality_mult(item.quality) * max(0.3, mult)
    samples = max(5, 80 - core * 12 - high * 10 - (10 if item.quality and item.quality >= 90 else 0))
    return {
        "slot": item.slot,
        "name": item.name,
        "part": part,
        "partLabel": _part_label(part),
        "grade": item.grade,
        "tier": "T4 추정",
        "quality": item.quality,
        "qualityBand": _quality_band(item.quality),
        "coreEffectCount": core,
        "secondaryEffectCount": secondary,
        "matchedEffectCount": len(matched),
        "similarListingEstimate": {
            "minGold": _gold(median * 0.55),
            "q25Gold": _gold(median * 0.78),
            "medianGold": _gold(median),
            "q75Gold": _gold(median * 1.38),
            "sampleCount": samples,
            "sampleType": "synthetic_comparable_until_trade_api",
        },
        "matchingConditions": {
            "part": _part_label(part),
            "grade": item.grade or "등급 미상",
            "tier": "T4 추정",
            "qualityBand": _quality_band(item.quality),
            "coreEffectCount": core,
            "validEffectCount": len(targets),
        },
        "basis": "heuristic_market_reproduction_v1",
        "warning": "실제 유사 매물 조회 전까지는 품질과 유효옵션 수 기반 추정값입니다.",
    }


def _sum(items: list[dict[str, Any]], key: str) -> float:
    return sum(float((row.get("similarListingEstimate") or {}).get(key) or 0) for row in items)


def _bracelet_grade(item: EquipmentItem | None) -> str:
    return "relic" if "유물" in str(item.grade if item else "") else "ancient"


def _bracelet(character: CharacterSummary, official: dict[str, Any] | None, memory: dict[str, Any] | None) -> dict[str, Any]:
    item = next((row for row in character.accessories if row.slot == "팔찌"), None)
    if not item:
        return {"available": False, "reason": "조회된 팔찌가 없습니다."}
    grade = _bracelet_grade(item)
    base_price = {"ancient": 200000.0, "relic": 60000.0}.get(grade, 200000.0)
    reroll_price = {"ancient": 14000.0, "relic": 7000.0}.get(grade, 14000.0)
    hint = (memory or {}).get("braceletAcquisition") or {}
    attempts = _i(hint.get("attempts"))
    expected_attempts = _n(((official or {}).get("randomOptionBasis") or {}).get("expectedAttempts"), 0.0) or None
    actual = base_price + reroll_price * attempts if attempts is not None else None
    expected = base_price + reroll_price * expected_attempts if expected_attempts is not None else None
    return {
        "available": True,
        "name": item.name,
        "grade": grade,
        "gradeLabel": (official or {}).get("gradeLabel") or ("유물" if grade == "relic" else "고대"),
        "baseBraceletPriceGold": _gold(base_price),
        "rerollStonePriceGold": _gold(reroll_price),
        "userAttempts": attempts,
        "userMode": hint.get("mode") or "unknown",
        "estimatedActualCostGold": _gold(actual),
        "expectedAttempts": expected_attempts,
        "expectedRerollCostGold": _gold(reroll_price * expected_attempts) if expected_attempts is not None else None,
        "expectedReproductionCostGold": _gold(expected),
        "formula": "베이스 팔찌 가격 + 팔찌 돌 가격 × 시도 수",
        "basis": "base_plus_reroll_stone_model_v1",
        "warning": "팔찌 가격은 v60 기본값입니다. 실제 가격 조회 연동 후 교체해야 합니다.",
    }


def build_market_cost_summary(character: CharacterSummary, official_accessory: dict[str, Any] | None, official_bracelet: dict[str, Any] | None, memory_hints: dict[str, Any] | None) -> dict[str, Any]:
    accessory_rows = [item for item in character.accessories if item.slot != "팔찌"]
    official_rows = (official_accessory or {}).get("items") or []
    items = [_accessory_item(item, official_rows[idx] if idx < len(official_rows) else None) for idx, item in enumerate(accessory_rows)]
    total = {
        "minGold": _gold(_sum(items, "minGold")),
        "q25Gold": _gold(_sum(items, "q25Gold")),
        "medianGold": _gold(_sum(items, "medianGold")),
        "q75Gold": _gold(_sum(items, "q75Gold")),
        "itemCount": len(items),
    }
    bracelet = _bracelet(character, official_bracelet, memory_hints)
    bracelet_cost = bracelet.get("estimatedActualCostGold") or bracelet.get("expectedReproductionCostGold") or 0
    return {
        "version": "v60-market-cost-model",
        "source": "heuristic_until_trade_or_auction_api",
        "tradeApiConnected": False,
        "summary": {
            "accessoryMedianGold": total["medianGold"],
            "braceletActualGold": bracelet.get("estimatedActualCostGold"),
            "braceletExpectedGold": bracelet.get("expectedReproductionCostGold"),
            "marketReproductionGold": _gold(float(total.get("medianGold") or 0) + float(bracelet_cost or 0)),
        },
        "accessoryMarket": {
            "items": items,
            "total": total,
            "conditions": ["부위", "등급", "티어", "품질 구간", "핵심 옵션 수", "유효 옵션 수"],
            "basis": "현재 장신구와 비슷한 조건의 시장 재현 비용 추정",
        },
        "braceletMarket": bracelet,
        "separationRule": {
            "cost": "시장 재현 비용은 구매/재구매 비용으로 표시합니다.",
            "luck": "운 판정은 장기백, 스톤 시도 수, 장신구 직접 연마 시도 수, 팔찌 랜덤 옵션 시도 수로 따로 봅니다.",
        },
        "limits": [
            "v60 1차는 실제 유사 매물 조회가 아니라 조건 기반 시장가 추정 모델입니다.",
            "장신구는 부위/품질/유효옵션 수를 이용해 하위 25%, 중앙값, 상위 25%를 추정합니다.",
            "팔찌는 베이스 팔찌 가격과 팔찌 돌 가격 × 시도 수를 분리합니다.",
            "운 판정과 시장 구매 비용은 한 점수로 섞지 않습니다.",
        ],
    }
