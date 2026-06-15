from __future__ import annotations

import re
from typing import Any

from app.core.settings import get_settings
from app.models.schemas import CharacterSummary, EquipmentItem
from app.services.lostark_client import LostArkClient

AUCTION_PAGE_LIMIT = 30


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


def _quality_floor(q: int | None) -> int:
    if q is None:
        return 0
    if q >= 95:
        return 95
    if q >= 90:
        return 90
    if q >= 80:
        return 80
    if q >= 70:
        return 70
    return 0


def _quality_band_key(q: int | None) -> str:
    return _quality_band(q)


def _auction_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        items = data.get("Items") or data.get("items")
        return [row for row in items if isinstance(row, dict)] if isinstance(items, list) else []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _normalize_name(value: Any) -> str:
    text = str(value or "")
    text = text.replace(" ", "")
    text = text.replace("%", "")
    text = text.replace("+", "")
    return text.lower()


def _first_number(text: str) -> float | None:
    match = re.search(r"[+＋-]?(\d+(?:\.\d+)?)", str(text or ""))
    return float(match.group(1)) if match else None


def _desired_option_from_effect(effect: str) -> dict[str, Any] | None:
    text = str(effect or "")
    value = _first_number(text)
    if value is None:
        return None
    names = [
        "적에게 주는 피해",
        "추가 피해",
        "치명타 적중률",
        "치명타 피해",
        "아군 공격력 강화 효과",
        "아군 피해량 강화 효과",
        "무기 공격력",
        "공격력",
        "낙인력",
        "세레나데",
        "신앙",
        "조화 게이지",
    ]
    for name in names:
        if name in text:
            return {"name": name, "value": value, "isPercent": "%" in text, "raw": text}
    return None


def _desired_priority(part: str, option: dict[str, Any]) -> int:
    name = str(option.get("name") or "")
    is_percent = bool(option.get("isPercent"))
    if part == "necklace":
        if name == "추가 피해":
            return 1
        if name == "적에게 주는 피해":
            return 2
        if name == "낙인력":
            return 3
        if name in {"세레나데", "신앙", "조화 게이지"}:
            return 4
        if name == "무기 공격력":
            return 5
        if name == "공격력":
            return 6
    if part == "earring":
        if name == "무기 공격력" and is_percent:
            return 1
        if name == "공격력" and is_percent:
            return 2
        if name == "무기 공격력":
            return 5
        if name == "공격력":
            return 6
    if part == "ring":
        if name == "치명타 피해":
            return 1
        if name == "치명타 적중률":
            return 2
        if name == "아군 공격력 강화 효과":
            return 3
        if name == "아군 피해량 강화 효과":
            return 4
        if name == "무기 공격력":
            return 5
        if name == "공격력":
            return 6
    return 99


def _desired_options(item: EquipmentItem) -> list[dict[str, Any]]:
    effects = item.accessory_effects or []
    rows = [row for row in (_desired_option_from_effect(str(effect)) for effect in effects) if row]
    part = _part(item.slot)
    rows = sorted(rows, key=lambda row: (_desired_priority(part, row), -float(row.get("value") or 0)))
    return rows[:2]


def _auction_option_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    options = row.get("Options") or row.get("options") or []
    return [option for option in options if isinstance(option, dict)] if isinstance(options, list) else []


def _auction_buy_price(row: dict[str, Any]) -> float | None:
    info = row.get("AuctionInfo") or row.get("auctionInfo") or {}
    if not isinstance(info, dict):
        return None
    value = info.get("BuyPrice") if "BuyPrice" in info else info.get("buyPrice")
    try:
        parsed = float(value)
        return parsed if parsed > 0 else None
    except Exception:
        return None


def _same_quality_band(row: dict[str, Any], quality: int | None) -> bool:
    if quality is None:
        return True
    raw = row.get("GradeQuality") if "GradeQuality" in row else row.get("gradeQuality")
    try:
        return _quality_band_key(int(raw)) == _quality_band_key(int(quality))
    except Exception:
        return False


def _option_matches(desired: dict[str, Any], option: dict[str, Any]) -> bool:
    option_name = _normalize_name(option.get("OptionName") or option.get("optionName"))
    desired_name = _normalize_name(desired.get("name"))
    if desired_name not in option_name and option_name not in desired_name:
        return False
    try:
        option_value = float(option.get("Value") if "Value" in option else option.get("value"))
    except Exception:
        return False
    if abs(option_value - float(desired["value"])) > 0.001:
        return False
    expected_percent = bool(desired.get("isPercent"))
    actual_percent = bool(option.get("IsValuePercentage") if "IsValuePercentage" in option else option.get("isValuePercentage"))
    return expected_percent == actual_percent


def _auction_item_matches_current_accessory(row: dict[str, Any], item: EquipmentItem, desired: list[dict[str, Any]]) -> bool:
    if item.name and str(row.get("Name") or row.get("name") or "") != str(item.name):
        return False
    if item.grade and str(row.get("Grade") or row.get("grade") or "") != str(item.grade):
        return False
    if not _same_quality_band(row, item.quality):
        return False
    options = _auction_option_rows(row)
    if not desired or not options:
        return False
    return all(any(_option_matches(target, option) for option in options) for target in desired)


def _auction_prices(items: list[dict[str, Any]], item: EquipmentItem, desired: list[dict[str, Any]]) -> list[float]:
    prices: list[float] = []
    for row in items:
        if not _auction_item_matches_current_accessory(row, item, desired):
            continue
        value = _auction_buy_price(row)
        if value is not None:
            prices.append(float(value))
    return sorted(prices)


def _auction_payload(item: EquipmentItem, part: str, page_no: int = 1) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "CategoryCode": _auction_category_code(part),
        "ItemName": item.name or "",
        "ItemGrade": item.grade or "고대",
        "ItemTier": 4,
        "PageNo": page_no,
        "Sort": "BUY_PRICE",
        "SortCondition": "ASC",
    }
    quality_floor = _quality_floor(item.quality)
    if quality_floor > 0:
        payload["ItemGradeQuality"] = quality_floor
    return payload


def _search_cache_key(item: EquipmentItem, part: str, request_label: str) -> tuple[Any, ...]:
    # 사용자가 보는 장착 슬롯 단위로 별도 API 스캔을 수행합니다.
    # 예: 목걸이, 귀걸이1, 귀걸이2, 반지1, 반지2.
    return (
        request_label,
        _auction_category_code(part),
        item.name or "",
        item.grade or "고대",
        4,
        _quality_floor(item.quality),
    )


def _failed_estimate(reason: str, sample_type: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    result = {
        "minGold": None,
        "q25Gold": None,
        "medianGold": None,
        "q75Gold": None,
        "sampleCount": 0,
        "sampleType": sample_type,
        "status": "failed",
        "failureReason": reason,
    }
    if details:
        result["debug"] = details
    return result


def _search_auction_pages(
    client: LostArkClient,
    item: EquipmentItem,
    part: str,
    request_label: str,
    search_cache: dict[tuple[Any, ...], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    cache_key = _search_cache_key(item, part, request_label)
    if cache_key in search_cache:
        return search_cache[cache_key]

    rows: list[dict[str, Any]] = []
    for page_no in range(1, AUCTION_PAGE_LIMIT + 1):
        data = client.search_auction_items(_auction_payload(item, part, page_no), optional=True)
        page_items = _auction_items(data)
        if not page_items:
            break
        rows.extend(page_items)
    search_cache[cache_key] = rows
    return rows


def _auction_estimate(
    item: EquipmentItem,
    part: str,
    request_label: str,
    search_cache: dict[tuple[Any, ...], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    desired = _desired_options(item)
    if not desired:
        return _failed_estimate("현재 장신구에서 비교할 핵심 연마 옵션을 찾지 못했습니다.", "auction_option_parse_failed")
    if not get_settings().lostark_api_key:
        return _failed_estimate("경매장 인증 설정이 없어 조회하지 못했습니다.", "auction_missing_auth")
    if search_cache is None:
        search_cache = {}
    cache_key = _search_cache_key(item, part, request_label)
    try:
        client = LostArkClient()
        raw_items = _search_auction_pages(client, item, part, request_label, search_cache)
    except Exception:
        return _failed_estimate("경매장 요청에 실패했습니다.", "auction_request_failed")
    debug = {
        "requestLabel": request_label,
        "rawItemCount": len(raw_items),
        "pageLimit": AUCTION_PAGE_LIMIT,
        "qualityFloor": _quality_floor(item.quality),
        "cacheKey": list(cache_key),
        "desiredOptions": [row.get("raw") for row in desired],
    }
    if not raw_items:
        return _failed_estimate("최근 매물 없음", "auction_recent_listing_not_found", debug)
    prices = _auction_prices(raw_items, item, desired)
    if not prices:
        return _failed_estimate("최근 매물 없음", "auction_recent_listing_not_found", debug)
    median = prices[len(prices) // 2]
    q25 = prices[max(0, len(prices) // 4)]
    q75 = prices[min(len(prices) - 1, (len(prices) * 3) // 4)]
    return {
        "minGold": _gold(prices[0]),
        "q25Gold": _gold(q25),
        "medianGold": _gold(median),
        "q75Gold": _gold(q75),
        "sampleCount": len(prices),
        "sampleType": "lostark_auction_api_per_accessory_paged",
        "status": "ok",
        "failureReason": None,
        "debug": debug,
    }


def _accessory_item(
    item: EquipmentItem,
    official: dict[str, Any] | None,
    request_label: str,
    search_cache: dict[tuple[Any, ...], list[dict[str, Any]]],
) -> dict[str, Any]:
    part = str((official or {}).get("part") or _part(item.slot))
    targets = (official or {}).get("targetEffects") or []
    matched = (official or {}).get("matchedEffects") or []
    core = sum(1 for row in targets if row.get("isCore"))
    secondary = sum(1 for row in targets if row.get("isSecondary"))
    estimate = _auction_estimate(item, part, request_label, search_cache)
    ok = estimate.get("status") == "ok"
    return {
        "slot": item.slot,
        "marketRequestLabel": request_label,
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
            "requestLabel": request_label,
            "part": _part_label(part),
            "grade": item.grade or "등급 미상",
            "tier": "T4 추정",
            "qualityBand": _quality_band(item.quality),
            "coreEffectCount": core,
            "validEffectCount": len(targets),
        },
        "basis": "lostark_auction_api_per_accessory_paged" if ok else "lostark_auction_api_failed_no_fallback",
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


def _accessory_request_labels(accessory_rows: list[EquipmentItem]) -> list[str]:
    part_counts: dict[str, int] = {}
    labels: list[str] = []
    for item in accessory_rows:
        part = _part(item.slot)
        label = _part_label(part)
        part_counts[part] = part_counts.get(part, 0) + 1
        if part in {"earring", "ring"}:
            label = f"{label}{part_counts[part]}"
        labels.append(label)
    return labels


def build_market_cost_summary(character: CharacterSummary, official_accessory: dict[str, Any] | None, official_bracelet: dict[str, Any] | None, memory_hints: dict[str, Any] | None) -> dict[str, Any]:
    accessory_rows = [item for item in character.accessories if item.slot != "팔찌"]
    official_rows = (official_accessory or {}).get("items") or []
    request_labels = _accessory_request_labels(accessory_rows)
    search_cache: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    items = [
        _accessory_item(
            item,
            official_rows[idx] if idx < len(official_rows) else None,
            request_labels[idx] if idx < len(request_labels) else f"장신구{idx + 1}",
            search_cache,
        )
        for idx, item in enumerate(accessory_rows)
    ]
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
        "version": "v60.11-auction-per-equipped-accessory",
        "source": "lostark_auction_api_per_equipped_accessory_no_fallback",
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
            "conditions": ["목걸이", "귀걸이1", "귀걸이2", "반지1", "반지2", "각 장착 장신구별 별도 API 스캔", f"상위 {AUCTION_PAGE_LIMIT}페이지"],
            "basis": "장착 중인 각 장신구를 목걸이/귀걸이1/귀걸이2/반지1/반지2 단위로 분리해 /auctions/items를 별도로 조회합니다. 이후 해당 장신구의 가격 우선 핵심 옵션과 일치하는 즉시 구매 매물만 사용합니다.",
        },
        "braceletMarket": bracelet,
        "separationRule": {
            "cost": "시장 재현 비용은 구매/재구매 비용으로 표시합니다.",
            "luck": "운 판정은 장기백, 스톤 시도 수, 장신구 직접 연마 시도 수, 팔찌 랜덤 옵션 시도 수로 따로 봅니다.",
        },
        "limits": [
            f"각 장착 장신구는 별도 요청 라벨로 경매장 상위 {AUCTION_PAGE_LIMIT}페이지를 스캔합니다.",
            "요청 라벨은 목걸이, 귀걸이1, 귀걸이2, 반지1, 반지2입니다.",
            "같은 이름/등급/품질이라도 장착 슬롯이 다르면 API 스캔 단위를 공유하지 않습니다.",
            "조건에 맞는 매물이 없으면 장신구 시장가는 최근 매물 없음으로 표시합니다.",
            "입찰가, 시작가, 옵션 불일치 매물 가격은 시장 재현 비용으로 사용하지 않습니다.",
            "팔찌 가격은 후속 연동 대상입니다.",
        ],
    }
