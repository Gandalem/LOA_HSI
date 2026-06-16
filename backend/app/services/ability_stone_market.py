from __future__ import annotations

from typing import Any

from app.core.settings import get_settings
from app.models.schemas import AbilityStoneSummary, CharacterSummary
from app.services.lostark_client import LostArkClient

ABILITY_STONE_CATEGORY_CODE = 30000
STONE_AUCTION_PAGE_LIMIT = 5


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


def _row_text(row: dict[str, Any]) -> str:
    parts: list[str] = [str(row.get("Name") or row.get("name") or "")]
    options = row.get("Options") or row.get("options") or []
    if isinstance(options, list):
        for option in options:
            if not isinstance(option, dict):
                continue
            parts.append(str(option.get("OptionName") or option.get("optionName") or ""))
            parts.append(str(option.get("OptionNameTripod") or option.get("optionNameTripod") or ""))
            parts.append(str(option.get("Value") if "Value" in option else option.get("value") or ""))
    return " ".join(parts)


def _stone_match_score(row: dict[str, Any], stone: AbilityStoneSummary | None) -> int:
    if not stone:
        return 0
    text = _row_text(row)
    score = 0
    for name in (stone.positive_1_name, stone.positive_2_name):
        clean = str(name or "").strip()
        if clean and clean in text:
            score += 1
    return score


def _payload(stone: AbilityStoneSummary | None, page_no: int, use_name: bool) -> dict[str, Any]:
    grade = (stone.grade if stone and stone.grade else "고대")
    name = str(stone.name or "").strip() if stone else ""
    # The auction endpoint is more stable when optional schema fields are present as null/empty arrays.
    return {
        "ItemLevelMin": None,
        "ItemLevelMax": None,
        "ItemGradeQuality": None,
        "ItemUpgradeLevel": None,
        "ItemTradeAllowCount": None,
        "SkillOptions": [],
        "EtcOptions": [],
        "Sort": "BUY_PRICE",
        "CategoryCode": ABILITY_STONE_CATEGORY_CODE,
        "CharacterClass": None,
        "ItemTier": 4,
        "ItemGrade": grade,
        "ItemName": name if use_name and name else None,
        "PageNo": page_no,
        "SortCondition": "ASC",
    }


def _search_rows(client: LostArkClient, stone: AbilityStoneSummary | None, use_name: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    payloads: list[dict[str, Any]] = []
    for page_no in range(1, STONE_AUCTION_PAGE_LIMIT + 1):
        payload = _payload(stone, page_no, use_name)
        payloads.append(payload)
        page_items = _auction_items(client.search_auction_items(payload, optional=True))
        if not page_items:
            break
        rows.extend(page_items)
    return rows, payloads


def _price_summary(prices: list[float]) -> dict[str, Any]:
    if not prices:
        return {
            "minGold": None,
            "q25Gold": None,
            "medianGold": None,
            "q75Gold": None,
            "sampleCount": 0,
        }
    values = sorted(float(x) for x in prices)
    return {
        "minGold": _gold(values[0]),
        "q25Gold": _gold(values[max(0, len(values) // 4)]),
        "medianGold": _gold(values[len(values) // 2]),
        "q75Gold": _gold(values[min(len(values) - 1, (len(values) * 3) // 4)]),
        "sampleCount": len(values),
    }


def _debug_sample(rows: list[dict[str, Any]], stone: AbilityStoneSummary | None, limit: int = 5) -> list[dict[str, Any]]:
    sample: list[dict[str, Any]] = []
    for row in rows[:limit]:
        info = row.get("AuctionInfo") or row.get("auctionInfo") or {}
        sample.append({
            "name": row.get("Name") or row.get("name"),
            "grade": row.get("Grade") or row.get("grade"),
            "tier": row.get("Tier") or row.get("tier"),
            "buyPrice": info.get("BuyPrice") if isinstance(info, dict) else None,
            "matchScore": _stone_match_score(row, stone),
            "options": row.get("Options") or row.get("options") or [],
        })
    return sample


def build_ability_stone_market_summary(character: CharacterSummary, fallback_price_gold: float = 5000.0) -> dict[str, Any]:
    stone = character.ability_stone
    if not stone:
        return {
            "version": "v60.20-stone-auction-market",
            "source": "lostark_auction_api_ability_stone",
            "status": "failed",
            "failureReason": "조회된 어빌리티 스톤이 없습니다.",
            "unitPriceGold": _gold(float(fallback_price_gold)),
            "fallbackApplied": True,
            "fallbackPriceGold": _gold(float(fallback_price_gold)),
        }

    if not get_settings().lostark_api_key:
        return {
            "version": "v60.20-stone-auction-market",
            "source": "lostark_auction_api_ability_stone",
            "status": "failed",
            "failureReason": "경매장 인증 설정이 없어 기본 스톤 가격을 사용합니다.",
            "unitPriceGold": _gold(float(fallback_price_gold)),
            "fallbackApplied": True,
            "fallbackPriceGold": _gold(float(fallback_price_gold)),
        }

    client = LostArkClient()
    # First try the exact item name when the character API provides one. If that gives no rows,
    # fall back to grade/tier/category-only search and then verify engraving names from Options.
    rows, payloads = _search_rows(client, stone, use_name=True)
    if not rows:
        rows, payloads = _search_rows(client, stone, use_name=False)

    all_prices = [price for price in (_auction_buy_price(row) for row in rows) if price is not None]
    matched_rows = [row for row in rows if _stone_match_score(row, stone) >= 2]
    matched_prices = [price for price in (_auction_buy_price(row) for row in matched_rows) if price is not None]

    using_matched = bool(matched_prices)
    prices = matched_prices if using_matched else all_prices
    summary = _price_summary(prices)
    ok = bool(prices)
    unit_price = summary.get("medianGold") if ok else _gold(float(fallback_price_gold))

    return {
        "version": "v60.20-stone-auction-market",
        "source": "lostark_auction_api_ability_stone",
        "status": "ok" if ok else "failed",
        "failureReason": None if ok else "최근 스톤 매물 없음",
        "unitPriceGold": unit_price,
        "fallbackApplied": not ok,
        "fallbackPriceGold": _gold(float(fallback_price_gold)),
        "targetStone": {
            "name": stone.name,
            "grade": stone.grade,
            "positive1": stone.positive_1_name,
            "positive2": stone.positive_2_name,
            "negative": stone.negative_name,
            "stoneType": stone.stone_type,
        },
        "unitPrice": summary,
        "matchingMode": "engraving_options_verified" if using_matched else "category_grade_tier" if ok else "fallback_default",
        "matchingConditions": {
            "categoryCode": ABILITY_STONE_CATEGORY_CODE,
            "grade": stone.grade or "고대",
            "tier": 4,
            "itemNameTried": bool(stone.name),
            "positiveEngravings": [stone.positive_1_name, stone.positive_2_name],
            "pageLimit": STONE_AUCTION_PAGE_LIMIT,
            "sort": "BUY_PRICE ASC",
        },
        "debug": {
            "rawItemCount": len(rows),
            "matchedItemCount": len(matched_rows),
            "requestPayloadSample": payloads[0] if payloads else None,
            "rejectedOrSampleRows": _debug_sample(rows, stone),
        },
        "basis": "어빌리티 스톤 1개 단가를 경매장 즉시구매가 기준으로 잡고, 목표 스톤 확률의 기대 스톤 개수에 곱합니다.",
    }


def stone_market_unit_price(summary: dict[str, Any] | None, fallback_price_gold: float = 5000.0) -> float:
    if isinstance(summary, dict):
        value = summary.get("unitPriceGold")
        try:
            if value is not None and float(value) > 0:
                return float(value)
        except Exception:
            pass
    return float(fallback_price_gold)
