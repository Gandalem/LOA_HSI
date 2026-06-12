from __future__ import annotations

from typing import Any

from app.core.settings import get_settings
from app.models.schemas import CharacterSummary, EquipmentItem
from app.services.lostark_client import LostArkClient


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


def _auction_category_code(part: str) -> int | None:
    return {"necklace": 200010, "earring": 200020, "ring": 200030}.get(part)


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


def _find_numeric(obj: Any, keys: list[str]) -> float | None:
    if isinstance(obj, dict):
        for key in keys:
            if key in obj and obj[key] is not None:
                try:
                    return float(str(obj[key]).replace(",", ""))
                except Exception:
                    pass
        for value in obj.values():
            found = _find_numeric(value, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _find_numeric(value, keys)
            if found is not None:
                return found
    return None


def _auction_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        items = data.get("Items") or data.get("items")
        return [row for row in items if isinstance(row, dict)] if isinstance(items, list) else []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _auction_prices(data: Any) -> list[float]:
    prices: list[float] = []
    for row in _auction_items(data):
        value = _find_numeric(row, ["BuyPrice", "buyPrice", "CurrentMinPrice", "currentMinPrice", "BidStartPrice", "bidStartPrice"])
        if value is not None and value > 0:
            prices.append(float(value))
    return sorted(prices)


def _auction_payload(item: EquipmentItem, part: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ItemLevelMin": 0,
        "ItemLevelMax": 1800,
        "ItemGradeQuality": int(item.quality or 0),
        "SkillOptions": [],
        "EtcOptions": [],
        "Sort": "BUY_PRICE",
        "CategoryCode": _auction_category_code(part),
        "CharacterClass": "",
        "ItemTier": 4,
        "ItemGrade": item.grade or "고대",
        "ItemName": item.name or "",
        "PageNo": 1,
        "SortCondition": "ASC",
    }
    return {key: value for key, value in payload.items() if value not in (None, "")}


def _failed_estimate(reason: str, sample_type: str) -> dict[str, Any]:
    return {
        "minGold": None,
        "q25Gold": None,
        "medianGold": None,
        "q75Gold": None,
        "sampleCount": 0,
        "sampleType": sample_type,
        "status": "failed",
        "failureReason": reason,
    }


def _auction_estimate(item: EquipmentItem, part: str) -> dict[str, Any]:
    if not get_settings().lostark_api_key:
        return _failed_estimate("경매장 인증 설정이 없어 조회하지 못했습니다.", "auction_missing_auth")
    try:
        data = LostArkClient().search_auction_items(_auction_payload(item, part), optional=True)
    except Exception:
        return _failed_estimate("경매장 요청에 실패했습니다.", "auction_request_failed")
    if data is None:
        return _failed_estimate("경매장 응답이 비어 있습니다.", "auction_empty_response")
    prices = _auction_prices(data)
    if not prices:
        return _failed_estimate("조건에 맞는 경매장 매물이 없습니다.", "auction_no_listing")
    median = prices[len(prices) // 2]
    q25 = prices[max(0, len(prices) // 4)]
    q75 = prices[min(len(prices) - 1, (len(prices) * 3) // 4)]
    return {
        "minGold": _gold(prices[0]),
        "q25Gold": _gold(q25),
        "medianGold": _gold(median),
        "q75Gold": _gold(q75),
        "sampleCount": len(prices),
        "sampleType": "lostark_auction_api",
        "status": "ok",
        "failureReason": None,
    }


def _accessory_item(item: EquipmentItem, official: dict[str, Any] | None) -> dict[str, Any]:
    part = str((official or {}).get("part") or _part(item.slot))
    targets = (official or {}).get("targetEffects") or []
    matched = (official or {}).get("matchedEffects") or []
    core = sum(1 for row in targets if row.get("isCore"))
    secondary = sum(1 for row in targets if row.get("isSecondary"))
    estimate = _auction_estimate(item, part)
    ok = estimate.get("status") == "ok"
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
        "similarListingEstimate": estimate,
        "matchingConditions": {
            "part": _part_label(part),
            "grade": item.grade or "등급 미상",
            "tier": "T4 추정",
            "qualityBand": _quality_band(item.quality),
            "coreEffectCount": core,
            "validEffectCount": len(targets),
        },
        "basis": "lostark_auction_api" if ok else "lostark_auction_api_failed_no_fallback",
        "warning": None if ok else estimate.get("failureReason"),
    }


def _sum_available(items: list[dict[str, Any]], key: str) -> float | None:
    if not items:
        return None
    total = 0.0
    for row in items:
        value = (row.get("similarListingEstimate") or {}).get(key)
        if value is None:
            return None
        total += float(value)
    return total


def _bracelet_grade(item: EquipmentItem | None) -> str:
    return "relic" if "유물" in str(item.grade if item else "") else "ancient"


def _bracelet(character: CharacterSummary, official: dict[str, Any] | None, memory: dict[str, Any] | None) -> dict[str, Any]:
    item = next((row for row in character.accessories if row.slot == "팔찌"), None)
    if not item:
        return {"available": False, "reason": "조회된 팔찌가 없습니다."}
    grade = _bracelet_grade(item)
    base_price = {"ancient": 30000.0, "relic": 10000.0}.get(grade, 30000.0)
    reroll_price = {"ancient": 200.0, "relic": 100.0}.get(grade, 200.0)
    hint = (memory or {}).get("braceletAcquisition") or {}
    mode = hint.get("mode") or "unknown"
    attempts = _i(hint.get("attempts"))
    expected_attempts = _n(((official or {}).get("randomOptionBasis") or {}).get("expectedAttempts"), 0.0) or None
    actual_base = 0.0 if mode == "self_obtained" else base_price
    actual = actual_base + reroll_price * attempts if attempts is not None else None
    expected = base_price + reroll_price * expected_attempts if expected_attempts is not None else None
    return {
        "available": True,
        "name": item.name,
        "grade": grade,
        "gradeLabel": (official or {}).get("gradeLabel") or ("유물" if grade == "relic" else "고대"),
        "baseBraceletPriceGold": _gold(base_price),
        "actualBaseCostAppliedGold": _gold(actual_base) if attempts is not None else None,
        "rerollStonePriceGold": _gold(reroll_price),
        "userAttempts": attempts,
        "userMode": mode,
        "estimatedActualCostGold": _gold(actual),
        "expectedAttempts": expected_attempts,
        "expectedRerollCostGold": _gold(reroll_price * expected_attempts) if expected_attempts is not None else None,
        "expectedReproductionCostGold": _gold(expected),
        "formula": "기억 기반 비용 = 적용 베이스 비용 + 팔찌 돌 가격 × 시도 수. 직접 획득 팔찌는 베이스 비용을 0G로 봅니다.",
        "basis": "observed_scale_base_plus_reroll_stone_model_v1_1",
        "warning": "팔찌 가격은 임시 기본값입니다. 장신구 경매장 연동과 별개로 후속 연동 대상입니다.",
    }


def build_market_cost_summary(character: CharacterSummary, official_accessory: dict[str, Any] | None, official_bracelet: dict[str, Any] | None, memory_hints: dict[str, Any] | None) -> dict[str, Any]:
    accessory_rows = [item for item in character.accessories if item.slot != "팔찌"]
    official_rows = (official_accessory or {}).get("items") or []
    items = [_accessory_item(item, official_rows[idx] if idx < len(official_rows) else None) for idx, item in enumerate(accessory_rows)]
    connected_count = sum(1 for row in items if ((row.get("similarListingEstimate") or {}).get("status") == "ok"))
    all_prices_ok = bool(items) and connected_count == len(items)
    total = {
        "minGold": _gold(_sum_available(items, "minGold")),
        "q25Gold": _gold(_sum_available(items, "q25Gold")),
        "medianGold": _gold(_sum_available(items, "medianGold")),
        "q75Gold": _gold(_sum_available(items, "q75Gold")),
        "itemCount": len(items),
        "auctionConnectedItemCount": connected_count,
        "status": "ok" if all_prices_ok else "failed",
    }
    bracelet = _bracelet(character, official_bracelet, memory_hints)
    bracelet_cost = bracelet.get("estimatedActualCostGold") or bracelet.get("expectedReproductionCostGold") or 0
    accessory_median = total.get("medianGold")
    return {
        "version": "v60.3-auction-accessory-market-cost-strict",
        "source": "lostark_auction_api_no_fallback",
        "tradeApiConnected": all_prices_ok,
        "auctionApiConnected": connected_count > 0,
        "summary": {
            "accessoryMedianGold": accessory_median,
            "braceletActualGold": bracelet.get("estimatedActualCostGold"),
            "braceletExpectedGold": bracelet.get("expectedReproductionCostGold"),
            "marketReproductionGold": _gold(float(accessory_median) + float(bracelet_cost or 0)) if accessory_median is not None else None,
        },
        "accessoryMarket": {
            "items": items,
            "total": total,
            "conditions": ["부위", "등급", "티어", "품질", "아이템명"],
            "basis": "경매장 API 조회값만 사용합니다. 실패하거나 매물이 없으면 기존 보정값으로 대체하지 않습니다.",
        },
        "braceletMarket": bracelet,
        "separationRule": {
            "cost": "시장 재현 비용은 구매/재구매 비용으로 표시합니다.",
            "luck": "운 판정은 장기백, 스톤 시도 수, 장신구 직접 연마 시도 수, 팔찌 랜덤 옵션 시도 수로 따로 봅니다.",
        },
        "limits": [
            "장신구는 경매장 API 조회값만 사용합니다.",
            "인증 설정이 없거나 매물이 없으면 장신구 시장가는 실패로 표시합니다.",
            "현재 경매장 검색은 아이템명/부위/등급/품질 기준입니다. 세부 옵션 완전 일치 검색은 후속 보강 대상입니다.",
            "팔찌 가격은 후속 연동 대상입니다.",
            "운 판정과 시장 구매 비용은 한 점수로 섞지 않습니다.",
        ],
    }
