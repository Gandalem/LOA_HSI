from __future__ import annotations

import re
from typing import Any

from app.core.settings import get_settings
from app.models.schemas import CharacterSummary, EquipmentItem
from app.services.lostark_client import LostArkClient

AUCTION_PAGE_LIMIT = 30
QUALITY_TOLERANCE_PRIMARY = 5
QUALITY_TOLERANCE_FALLBACK = 10


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


def _quality_min_for_tolerance(q: int | None, tolerance: int) -> int:
    if q is None:
        return 0
    return max(0, min(100, int(q) - int(tolerance)))


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


def _quality_in_tolerance(row: dict[str, Any], quality: int | None, tolerance: int) -> bool:
    if quality is None:
        return True
    raw = row.get("GradeQuality") if "GradeQuality" in row else row.get("gradeQuality")
    try:
        return abs(int(raw) - int(quality)) <= int(tolerance)
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


def _auction_item_matches_current_accessory(row: dict[str, Any], item: EquipmentItem, desired: list[dict[str, Any]], quality_tolerance: int) -> bool:
    if item.name and str(row.get("Name") or row.get("name") or "") != str(item.name):
        return False
    if item.grade and str(row.get("Grade") or row.get("grade") or "") != str(item.grade):
        return False
    if not _quality_in_tolerance(row, item.quality, quality_tolerance):
        return False
    options = _auction_option_rows(row)
    if not desired or not options:
        return False
    return all(any(_option_matches(target, option) for option in options) for target in desired)


def _auction_prices(items: list[dict[str, Any]], item: EquipmentItem, desired: list[dict[str, Any]], quality_tolerance: int) -> list[float]:
    prices: list[float] = []
    for row in items:
        if not _auction_item_matches_current_accessory(row, item, desired, quality_tolerance):
            continue
        value = _auction_buy_price(row)
        if value is not None:
            prices.append(float(value))
    return sorted(prices)


def _option_code(row: dict[str, Any]) -> int | None:
    for key in ("Value", "value", "Code", "code", "Id", "id"):
        if key in row:
            try:
                return int(row[key])
            except Exception:
                return None
    return None


def _option_text(row: dict[str, Any]) -> str:
    for key in ("Text", "text", "Name", "name", "OptionName", "optionName"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _option_children(row: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("EtcSubs", "etcSubs", "Options", "options", "SubOptions", "subOptions", "Children", "children", "Subs", "subs"):
        value = row.get(key)
        if isinstance(value, list):
            return [child for child in value if isinstance(child, dict)]
    return []


def _auction_etc_option_candidates(auction_options: Any) -> list[dict[str, Any]]:
    if not isinstance(auction_options, dict):
        return []
    groups = auction_options.get("EtcOptions") or auction_options.get("etcOptions") or []
    if not isinstance(groups, list):
        return []
    candidates: list[dict[str, Any]] = []
    for parent in groups:
        if not isinstance(parent, dict):
            continue
        first = _option_code(parent)
        parent_text = _option_text(parent)
        if first is None:
            continue
        children = _option_children(parent)
        for child in children:
            second = _option_code(child)
            child_text = _option_text(child)
            if second is None:
                continue
            text = f"{parent_text} {child_text}".strip()
            candidates.append({"FirstOption": first, "SecondOption": second, "text": text, "parentText": parent_text, "childText": child_text})
    return candidates


def _auction_filter_score(desired: dict[str, Any], candidate: dict[str, Any]) -> int:
    desired_name = str(desired.get("name") or "")
    desired_norm = _normalize_name(desired_name)
    text = str(candidate.get("text") or "")
    text_norm = _normalize_name(text)
    if not desired_norm:
        return 0
    if desired_name == "공격력" and "무기공격력" in text_norm:
        return 0
    if desired_name == "무기 공격력" and "무기공격력" not in text_norm:
        return 0
    if desired_norm not in text_norm and text_norm not in desired_norm:
        return 0
    score = 100
    if desired_norm == text_norm or desired_norm == _normalize_name(candidate.get("childText")):
        score += 40
    is_percent = bool(desired.get("isPercent"))
    if is_percent and ("%" in text or "비율" in text or "퍼센트" in text):
        score += 25
    if not is_percent and ("+" in text or "수치" in text):
        score += 15
    if is_percent and "+" in text and "%" not in text:
        score -= 30
    if not is_percent and "%" in text:
        score -= 30
    return score


def _auction_etc_filter_for_desired(desired: dict[str, Any], auction_options: Any) -> dict[str, Any] | None:
    candidates = _auction_etc_option_candidates(auction_options)
    scored = [(candidate, _auction_filter_score(desired, candidate)) for candidate in candidates]
    scored = [(candidate, score) for candidate, score in scored if score > 0]
    if not scored:
        return None
    candidate = sorted(scored, key=lambda row: row[1], reverse=True)[0][0]
    value = float(desired.get("value") or 0)
    return {
        "FirstOption": candidate["FirstOption"],
        "SecondOption": candidate["SecondOption"],
        "MinValue": value,
        "MaxValue": value,
    }


def _auction_etc_filters(desired: list[dict[str, Any]], auction_options: Any) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    for row in desired:
        resolved = _auction_etc_filter_for_desired(row, auction_options)
        if resolved:
            filters.append(resolved)
    return filters


def _auction_payload(item: EquipmentItem, part: str, page_no: int = 1, desired: list[dict[str, Any]] | None = None, auction_options: Any = None, quality_tolerance: int = QUALITY_TOLERANCE_PRIMARY) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "CategoryCode": _auction_category_code(part),
        "ItemName": item.name or "",
        "ItemGrade": item.grade or "고대",
        "ItemTier": 4,
        "PageNo": page_no,
        "Sort": "BUY_PRICE",
        "SortCondition": "ASC",
    }
    quality_min = _quality_min_for_tolerance(item.quality, quality_tolerance)
    if quality_min > 0:
        payload["ItemGradeQuality"] = quality_min
    filters = _auction_etc_filters(desired or [], auction_options)
    if filters:
        payload["EtcOptions"] = filters
    return payload


def _search_cache_key(item: EquipmentItem, part: str, request_label: str, etc_filters: list[dict[str, Any]], quality_tolerance: int) -> tuple[Any, ...]:
    return (
        request_label,
        _auction_category_code(part),
        item.name or "",
        item.grade or "고대",
        4,
        _quality_min_for_tolerance(item.quality, quality_tolerance),
        quality_tolerance,
        tuple((row.get("FirstOption"), row.get("SecondOption"), row.get("MinValue"), row.get("MaxValue")) for row in etc_filters),
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
    desired: list[dict[str, Any]],
    auction_options: Any,
    search_cache: dict[tuple[Any, ...], list[dict[str, Any]]],
    quality_tolerance: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    etc_filters = _auction_etc_filters(desired, auction_options)
    cache_key = _search_cache_key(item, part, request_label, etc_filters, quality_tolerance)
    if cache_key in search_cache:
        return search_cache[cache_key], etc_filters

    rows: list[dict[str, Any]] = []
    for page_no in range(1, AUCTION_PAGE_LIMIT + 1):
        payload = _auction_payload(item, part, page_no, desired, auction_options, quality_tolerance)
        data = client.search_auction_items(payload, optional=True)
        page_items = _auction_items(data)
        if not page_items:
            break
        rows.extend(page_items)
    search_cache[cache_key] = rows
    return rows, etc_filters


def _quality_attempt_debug(
    item: EquipmentItem,
    request_label: str,
    cache_key: tuple[Any, ...],
    desired: list[dict[str, Any]],
    etc_filters: list[dict[str, Any]],
    raw_items: list[dict[str, Any]],
    quality_tolerance: int,
    auction_options: Any,
) -> dict[str, Any]:
    return {
        "requestLabel": request_label,
        "rawItemCount": len(raw_items),
        "pageLimit": AUCTION_PAGE_LIMIT,
        "qualityTolerance": quality_tolerance,
        "qualityMin": _quality_min_for_tolerance(item.quality, quality_tolerance),
        "qualityRange": [max(0, int(item.quality or 0) - quality_tolerance), min(100, int(item.quality or 0) + quality_tolerance)] if item.quality is not None else None,
        "qualityFallback": quality_tolerance > QUALITY_TOLERANCE_PRIMARY,
        "cacheKey": list(cache_key),
        "desiredOptions": [row.get("raw") for row in desired],
        "auctionEtcOptions": etc_filters,
        "auctionEtcOptionsResolved": len(etc_filters) == len(desired),
        "auctionOptionsEndpointLoaded": isinstance(auction_options, dict),
    }


def _auction_estimate(
    client: LostArkClient | None,
    auction_options: Any,
    item: EquipmentItem,
    part: str,
    request_label: str,
    search_cache: dict[tuple[Any, ...], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    desired = _desired_options(item)
    if not desired:
        return _failed_estimate("현재 장신구에서 비교할 핵심 연마 옵션을 찾지 못했습니다.", "auction_option_parse_failed")
    if not get_settings().lostark_api_key or client is None:
        return _failed_estimate("경매장 인증 설정이 없어 조회하지 못했습니다.", "auction_missing_auth")
    if search_cache is None:
        search_cache = {}

    last_debug: dict[str, Any] | None = None
    for quality_tolerance in (QUALITY_TOLERANCE_PRIMARY, QUALITY_TOLERANCE_FALLBACK):
        try:
            raw_items, etc_filters = _search_auction_pages(client, item, part, request_label, desired, auction_options, search_cache, quality_tolerance)
        except Exception:
            return _failed_estimate("경매장 요청에 실패했습니다.", "auction_request_failed")
        cache_key = _search_cache_key(item, part, request_label, etc_filters, quality_tolerance)
        debug = _quality_attempt_debug(item, request_label, cache_key, desired, etc_filters, raw_items, quality_tolerance, auction_options)
        last_debug = debug
        prices = _auction_prices(raw_items, item, desired, quality_tolerance)
        if not prices:
            continue
        median = prices[len(prices) // 2]
        q25 = prices[max(0, len(prices) // 4)]
        q75 = prices[min(len(prices) - 1, (len(prices) * 3) // 4)]
        return {
            "minGold": _gold(prices[0]),
            "q25Gold": _gold(q25),
            "medianGold": _gold(median),
            "q75Gold": _gold(q75),
            "sampleCount": len(prices),
            "sampleType": "lostark_auction_api_with_etc_options_quality_fallback" if quality_tolerance > QUALITY_TOLERANCE_PRIMARY else "lostark_auction_api_with_etc_options_quality_primary",
            "status": "ok",
            "failureReason": None,
            "warning": "품질 ±10 보조 참고가" if quality_tolerance > QUALITY_TOLERANCE_PRIMARY else None,
            "debug": debug,
        }

    return _failed_estimate("최근 매물 없음", "auction_recent_listing_not_found", last_debug)


def _accessory_item(
    client: LostArkClient | None,
    auction_options: Any,
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
    estimate = _auction_estimate(client, auction_options, item, part, request_label, search_cache)
    ok = estimate.get("status") == "ok"
    estimate_warning = estimate.get("warning")
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
            "primaryQualityTolerance": QUALITY_TOLERANCE_PRIMARY,
            "fallbackQualityTolerance": QUALITY_TOLERANCE_FALLBACK,
            "coreEffectCount": core,
            "validEffectCount": len(targets),
        },
        "basis": "lostark_auction_api_with_etc_options" if ok else "lostark_auction_api_failed_no_fallback",
        "warning": estimate_warning if ok and estimate_warning else (None if ok else estimate.get("failureReason")),
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
    client: LostArkClient | None = None
    auction_options: Any = None
    if get_settings().lostark_api_key:
        client = LostArkClient()
        auction_options = client.get_auction_options(optional=True)
    items = [
        _accessory_item(
            client,
            auction_options,
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
        "version": "v60.13-auction-quality-tolerance-fallback",
        "source": "lostark_auction_api_etc_options_quality_tolerance_no_fallback",
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
            "conditions": ["목걸이", "귀걸이1", "귀걸이2", "반지1", "반지2", "EtcOptions 요청 필터", "기본 품질 ±5", "실패 시 품질 ±10 보조", f"상위 {AUCTION_PAGE_LIMIT}페이지"],
            "basis": "각 장착 장신구별로 EtcOptions를 넣어 검색하고, 본 시장가는 현재 품질 ±5 범위에서 먼저 찾습니다. 없을 때만 ±10 범위를 보조 참고가로 사용합니다.",
        },
        "braceletMarket": bracelet,
        "separationRule": {
            "cost": "시장 재현 비용은 구매/재구매 비용으로 표시합니다.",
            "luck": "운 판정은 장기백, 스톤 시도 수, 장신구 직접 연마 시도 수, 팔찌 랜덤 옵션 시도 수로 따로 봅니다.",
        },
        "limits": [
            "본 시장가는 현재 품질 ±5 범위 매물을 우선 사용합니다.",
            "±5 범위에서 매칭 매물이 없을 때만 현재 품질 ±10 범위를 보조 참고가로 사용합니다.",
            "±10 보조 매물로 산정된 항목은 품질 ±10 보조 참고가로 표시합니다.",
            "장신구 핵심 옵션은 /auctions/items 요청의 EtcOptions에 포함해 검색합니다.",
            "응답 Options와 현재 장신구 옵션을 후처리로 한 번 더 검증합니다.",
            "조건에 맞는 매물이 없으면 장신구 시장가는 최근 매물 없음으로 표시합니다.",
            "입찰가, 시작가, 옵션 불일치 매물 가격은 시장 재현 비용으로 사용하지 않습니다.",
            "팔찌 가격은 후속 연동 대상입니다.",
        ],
    }
