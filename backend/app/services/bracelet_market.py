from __future__ import annotations

import re
from typing import Any

from app.core.settings import get_settings
from app.models.schemas import CharacterSummary, EquipmentItem
from app.services.lostark_client import LostArkClient

BRACELET_CATEGORY_CODE = 200040
BRACELET_PAGE_LIMIT = 10
VERSION = "v60.25-bracelet-fixed-effects-auction"
FIXED_BRACELET_SEARCH_LABEL = "4티어 고대 / 고정 효과만 / 금액 제한 없음 / 응답 Options 직접 검증"
COMBAT_STAT_NAMES = ["치명", "특화", "제압", "신속", "인내", "숙련"]
BASIC_FIXED_NAMES = ["힘", "민첩", "지능", "체력", "무기 공격력"]


def _n(value: Any, default: float = 0.0) -> float:
    try:
        return default if value is None else float(value)
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


def _auction_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        items = data.get("Items") or data.get("items")
        return [row for row in items if isinstance(row, dict)] if isinstance(items, list) else []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


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


def _normalize(value: Any) -> str:
    return str(value or "").replace(" ", "").replace("%", "").replace("+", "").lower()


def _first_number(text: Any) -> float | None:
    match = re.search(r"[+＋-]?(\d+(?:\.\d+)?)", str(text or ""))
    return float(match.group(1)) if match else None


def _clean_api_number(value: Any) -> int | float:
    parsed = float(value)
    return int(parsed) if parsed.is_integer() else parsed


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
    result: list[dict[str, Any]] = []
    for parent in groups:
        if not isinstance(parent, dict):
            continue
        first = _option_code(parent)
        parent_text = _option_text(parent)
        if first is None:
            continue
        for child in _option_children(parent):
            second = _option_code(child)
            child_text = _option_text(child)
            if second is None:
                continue
            values = child.get("EtcValues") or child.get("etcValues") or []
            result.append({
                "FirstOption": first,
                "SecondOption": second,
                "text": f"{parent_text} {child_text}".strip(),
                "childText": child_text,
                "values": values if isinstance(values, list) else [],
            })
    return result


def _auction_filter_score(desired: dict[str, Any], candidate: dict[str, Any]) -> int:
    desired_name = str(desired.get("name") or "")
    desired_norm = _normalize(desired_name)
    text = str(candidate.get("text") or "")
    text_norm = _normalize(text)
    if not desired_norm:
        return 0
    if desired_name == "공격력" and "무기공격력" in text_norm:
        return 0
    if desired_name == "무기 공격력" and "무기공격력" not in text_norm:
        return 0
    if desired_norm not in text_norm and text_norm not in desired_norm:
        return 0
    score = 100
    if desired_norm == _normalize(candidate.get("childText")):
        score += 60
    if "팔찌" in text:
        score += 20
    if any(name == desired_name for name in COMBAT_STAT_NAMES):
        score += 20
    return score


def _auction_filter_api_value(desired: dict[str, Any], candidate: dict[str, Any]) -> int | float:
    desired_value = float(desired.get("value") or 0)
    for row in candidate.get("values") or []:
        if not isinstance(row, dict):
            continue
        display_value = _first_number(row.get("DisplayValue") if "DisplayValue" in row else row.get("displayValue"))
        if display_value is not None and abs(display_value - desired_value) <= 0.001:
            raw = row.get("Value") if "Value" in row else row.get("value")
            if raw is not None:
                try:
                    return _clean_api_number(raw)
                except Exception:
                    pass
    return _clean_api_number(desired_value)


def _auction_etc_filter_for_desired(desired: dict[str, Any], auction_options: Any) -> dict[str, Any] | None:
    scored = [(row, _auction_filter_score(desired, row)) for row in _auction_etc_option_candidates(auction_options)]
    scored = [(row, score) for row, score in scored if score > 0]
    if not scored:
        return None
    candidate = sorted(scored, key=lambda row: row[1], reverse=True)[0][0]
    api_value = _auction_filter_api_value(desired, candidate)
    return {
        "FirstOption": candidate["FirstOption"],
        "SecondOption": candidate["SecondOption"],
        "MinValue": api_value,
        "MaxValue": api_value,
    }


def _bracelet_grade(item: EquipmentItem | None) -> str:
    return "relic" if "유물" in str(item.grade if item else "") else "ancient"


def _bracelet_grade_label(item: EquipmentItem | None, official: dict[str, Any] | None) -> str:
    return str((official or {}).get("gradeLabel") or ("유물" if _bracelet_grade(item) == "relic" else "고대"))


def _fixed_count_from_official(official: dict[str, Any] | None) -> int | None:
    purchase = (official or {}).get("purchaseStructure") or {}
    fixed_basis = purchase.get("fixedEffectBasis") or {}
    user_input = purchase.get("userInput") or {}
    for value in (
        user_input.get("fixedOptionCount"),
        fixed_basis.get("effectiveFixedOptionCount"),
        user_input.get("explicitFixedOptionCount"),
    ):
        parsed = _i(value)
        if parsed is not None and parsed > 0:
            return parsed
    return None


def _fixed_effects_from_official(official: dict[str, Any] | None) -> list[str]:
    fixed_count = _fixed_count_from_official(official)
    rows = (official or {}).get("matchedEffects") or []
    if not isinstance(rows, list):
        return []
    effects = [str(row.get("rawEffect") or "").strip() for row in rows if isinstance(row, dict) and row.get("rawEffect")]
    if fixed_count:
        return effects[:fixed_count]
    combat = [effect for effect in effects if any(effect.startswith(f"{name} ") or effect.startswith(f"{name}+") for name in COMBAT_STAT_NAMES)]
    return combat[:2]


def _desired_from_effect(effect: str) -> dict[str, Any] | None:
    value = _first_number(effect)
    if value is None:
        return None
    for name in COMBAT_STAT_NAMES + BASIC_FIXED_NAMES:
        if name in effect:
            return {"name": name, "value": value, "raw": effect}
    return None


def _fixed_desired_options(item: EquipmentItem, official: dict[str, Any] | None) -> list[dict[str, Any]]:
    effects = _fixed_effects_from_official(official)
    if not effects:
        effects = list(item.bracelet_effects or [])[:2]
    rows = [row for row in (_desired_from_effect(effect) for effect in effects) if row]
    seen: set[tuple[str, float]] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("name")), float(row.get("value") or 0))
        if key not in seen:
            unique.append(row)
            seen.add(key)
    return unique


def _auction_option_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    options = row.get("Options") or row.get("options") or []
    return [option for option in options if isinstance(option, dict)] if isinstance(options, list) else []


def _option_matches(desired: dict[str, Any], option: dict[str, Any]) -> bool:
    name = _normalize(option.get("OptionName") or option.get("optionName") or option.get("Name") or option.get("name"))
    desired_name = _normalize(desired.get("name"))
    if not name or (desired_name not in name and name not in desired_name):
        return False
    try:
        value = float(option.get("Value") if "Value" in option else option.get("value"))
    except Exception:
        return False
    return abs(value - float(desired.get("value") or 0)) <= 0.001


def _listing_matches(row: dict[str, Any], desired: list[dict[str, Any]], grade_label: str) -> bool:
    if grade_label and str(row.get("Grade") or row.get("grade") or "") != grade_label:
        return False
    options = _auction_option_rows(row)
    if not options:
        return False
    return all(any(_option_matches(target, option) for option in options) for target in desired)


def _payload(item: EquipmentItem, page_no: int, filters: list[dict[str, Any]], grade_label: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "CategoryCode": BRACELET_CATEGORY_CODE,
        "ItemGrade": grade_label,
        "ItemTier": 4,
        "PageNo": page_no,
        "Sort": "BUY_PRICE",
        "SortCondition": "ASC",
    }
    if filters:
        payload["EtcOptions"] = filters
    return payload


def _search_pages(client: LostArkClient, item: EquipmentItem, filters: list[dict[str, Any]], grade_label: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    payloads: list[dict[str, Any]] = []
    for page_no in range(1, BRACELET_PAGE_LIMIT + 1):
        payload = _payload(item, page_no, filters, grade_label)
        payloads.append(payload)
        page_items = _auction_items(client.search_auction_items(payload, optional=True))
        if not page_items:
            break
        rows.extend(page_items)
    return rows, payloads


def _price_summary(prices: list[float]) -> dict[str, Any]:
    if not prices:
        return {"minGold": None, "q25Gold": None, "medianGold": None, "q75Gold": None, "sampleCount": 0}
    values = sorted(float(value) for value in prices)
    return {
        "minGold": _gold(values[0]),
        "q25Gold": _gold(values[max(0, len(values) // 4)]),
        "medianGold": _gold(values[len(values) // 2]),
        "q75Gold": _gold(values[min(len(values) - 1, (len(values) * 3) // 4)]),
        "sampleCount": len(values),
    }


def _sample_rows(rows: list[dict[str, Any]], desired: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    sample: list[dict[str, Any]] = []
    for row in rows[:limit]:
        info = row.get("AuctionInfo") or row.get("auctionInfo") or {}
        sample.append({
            "name": row.get("Name") or row.get("name"),
            "grade": row.get("Grade") or row.get("grade"),
            "tier": row.get("Tier") or row.get("tier"),
            "buyPrice": info.get("BuyPrice") if isinstance(info, dict) else None,
            "options": _auction_option_rows(row),
            "matches": all(any(_option_matches(target, option) for option in _auction_option_rows(row)) for target in desired),
        })
    return sample


def _failed(item: EquipmentItem, official: dict[str, Any] | None, memory: dict[str, Any] | None, reason: str, desired: list[dict[str, Any]], filters: list[dict[str, Any]], raw_items: list[dict[str, Any]] | None = None, payloads: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    grade = _bracelet_grade(item)
    grade_label = _bracelet_grade_label(item, official)
    fallback_base = {"ancient": 30000.0, "relic": 10000.0}.get(grade, 30000.0)
    reroll_price = {"ancient": 200.0, "relic": 100.0}.get(grade, 200.0)
    hint = (memory or {}).get("braceletAcquisition") or {}
    attempts = _i(hint.get("attempts"))
    mode = hint.get("mode") or "unknown"
    expected_attempts = _n(((official or {}).get("randomOptionBasis") or {}).get("expectedAttempts"), 0.0) or None
    actual_base = 0.0 if mode == "self_obtained" else fallback_base
    actual = actual_base + reroll_price * attempts if attempts is not None else None
    expected = fallback_base + reroll_price * expected_attempts if expected_attempts is not None else None
    raw_items = raw_items or []
    payloads = payloads or []
    return {
        "available": True,
        "version": VERSION,
        "name": item.name,
        "grade": grade,
        "gradeLabel": grade_label,
        "baseBraceletPriceGold": _gold(fallback_base),
        "baseBraceletMarket": {
            "status": "failed",
            "failureReason": reason,
            "sampleType": "lostark_auction_api_bracelet_fixed_effects",
            "fixedEffects": [row.get("raw") for row in desired],
            "auctionEtcOptions": filters,
            "sampleCount": 0,
            "debug": {
                "categoryCode": BRACELET_CATEGORY_CODE,
                "searchCriteriaLabel": FIXED_BRACELET_SEARCH_LABEL,
                "rawItemCount": len(raw_items),
                "matchedItemCount": 0,
                "requestPayloadSample": payloads[0] if payloads else None,
                "sampleRows": _sample_rows(raw_items, desired),
            },
        },
        "actualBaseCostAppliedGold": _gold(actual_base) if attempts is not None else None,
        "rerollStonePriceGold": _gold(reroll_price),
        "userAttempts": attempts,
        "userMode": mode,
        "estimatedActualCostGold": _gold(actual),
        "expectedAttempts": expected_attempts,
        "expectedRerollCostGold": _gold(reroll_price * expected_attempts) if expected_attempts is not None else None,
        "expectedReproductionCostGold": _gold(expected),
        "formula": "기억 기반 비용 = 적용 베이스 비용 + 팔찌 돌 가격 × 시도 수. 직접 획득 팔찌는 베이스 비용을 0G로 봅니다.",
        "basis": "fallback_base_plus_reroll_stone_model",
        "warning": reason,
    }


def build_bracelet_fixed_market_summary(character: CharacterSummary, official: dict[str, Any] | None, memory: dict[str, Any] | None) -> dict[str, Any]:
    item = next((row for row in character.accessories if row.slot == "팔찌"), None)
    if not item:
        return {"available": False, "reason": "조회된 팔찌가 없습니다."}
    desired = _fixed_desired_options(item, official)
    if not desired:
        return _failed(item, official, memory, "팔찌 고정 효과를 파싱하지 못했습니다.", [], [])
    if not get_settings().lostark_api_key:
        return _failed(item, official, memory, "경매장 인증 설정이 없어 조회하지 못했습니다.", desired, [])

    client = LostArkClient()
    auction_options = client.get_auction_options(optional=True)
    filters = [row for row in (_auction_etc_filter_for_desired(desired_row, auction_options) for desired_row in desired) if row]
    if len(filters) != len(desired):
        return _failed(item, official, memory, "팔찌 고정 효과 검색 코드를 찾지 못했습니다.", desired, filters)

    grade = _bracelet_grade(item)
    grade_label = _bracelet_grade_label(item, official)
    try:
        raw_items, payloads = _search_pages(client, item, filters, grade_label)
    except Exception:
        return _failed(item, official, memory, "경매장 요청에 실패했습니다.", desired, filters)
    matched_rows = [row for row in raw_items if _listing_matches(row, desired, grade_label)]
    prices = sorted(price for price in (_auction_buy_price(row) for row in matched_rows) if price is not None)
    if not prices:
        return _failed(item, official, memory, "팔찌 고정 효과가 같은 최근 매물 없음", desired, filters, raw_items, payloads)

    price = _price_summary(prices)
    base_price = float(price.get("medianGold") or prices[len(prices) // 2])
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
        "version": VERSION,
        "name": item.name,
        "grade": grade,
        "gradeLabel": grade_label,
        "baseBraceletPriceGold": _gold(base_price),
        "baseBraceletMarket": {
            "status": "ok",
            "failureReason": None,
            "sampleType": "lostark_auction_api_bracelet_fixed_effects",
            "fixedEffects": [row.get("raw") for row in desired],
            "minGold": price.get("minGold"),
            "q25Gold": price.get("q25Gold"),
            "medianGold": price.get("medianGold"),
            "q75Gold": price.get("q75Gold"),
            "sampleCount": price.get("sampleCount"),
            "debug": {
                "categoryCode": BRACELET_CATEGORY_CODE,
                "searchCriteriaLabel": FIXED_BRACELET_SEARCH_LABEL,
                "rawItemCount": len(raw_items),
                "matchedItemCount": len(matched_rows),
                "pageLimit": BRACELET_PAGE_LIMIT,
                "itemNameIgnored": True,
                "priceFloorApplied": False,
                "auctionEtcOptions": filters,
                "requestPayloadSample": payloads[0] if payloads else None,
                "sampleRows": _sample_rows(raw_items, desired),
            },
        },
        "actualBaseCostAppliedGold": _gold(actual_base) if attempts is not None else None,
        "rerollStonePriceGold": _gold(reroll_price),
        "userAttempts": attempts,
        "userMode": mode,
        "estimatedActualCostGold": _gold(actual),
        "expectedAttempts": expected_attempts,
        "expectedRerollCostGold": _gold(reroll_price * expected_attempts) if expected_attempts is not None else None,
        "expectedReproductionCostGold": _gold(expected),
        "formula": "기억 기반 비용 = 적용 베이스 비용 + 팔찌 돌 가격 × 시도 수. 직접 획득 팔찌는 베이스 비용을 0G로 봅니다.",
        "basis": "lostark_auction_api_fixed_effect_base_plus_reroll_stone",
        "warning": None,
    }
