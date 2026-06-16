from __future__ import annotations

from typing import Any

from app.core.settings import get_settings
from app.models.schemas import AbilityStoneSummary, CharacterSummary
from app.services.lostark_client import LostArkClient

ABILITY_STONE_CATEGORY_CODE = 30000
STONE_AUCTION_PAGE_LIMIT = 5
VERSION = "v60.23-stone-same-positive-engravings"


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


def _stone_option_names(row: dict[str, Any]) -> list[str]:
    names: list[str] = []
    options = row.get("Options") or row.get("options") or []
    if isinstance(options, list):
        for option in options:
            if not isinstance(option, dict):
                continue
            if str(option.get("Type") or option.get("type") or "") != "ABILITY_ENGRAVE":
                continue
            if option.get("IsPenalty") or option.get("isPenalty"):
                continue
            name = str(option.get("OptionName") or option.get("optionName") or "").strip()
            if name:
                names.append(name)
    return names


def _target_positive_names(stone: AbilityStoneSummary | None) -> list[str]:
    if not stone:
        return []
    out: list[str] = []
    for name in (stone.positive_1_name, stone.positive_2_name):
        clean = str(name or "").strip()
        if clean and clean not in out:
            out.append(clean)
    return out


def _stone_match_score(row: dict[str, Any], stone: AbilityStoneSummary | None) -> int:
    names = _stone_option_names(row)
    return sum(1 for target in _target_positive_names(stone) if target in names)


def _same_positive_engravings(row: dict[str, Any], stone: AbilityStoneSummary | None) -> bool:
    targets = _target_positive_names(stone)
    if len(targets) < 2:
        return False
    names = _stone_option_names(row)
    return all(target in names for target in targets)


def _payload(stone: AbilityStoneSummary | None, page_no: int, use_name: bool) -> dict[str, Any]:
    grade = stone.grade if stone and stone.grade else "고대"
    name = str(stone.name or "").strip() if stone else ""
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
        return {"minGold": None, "q25Gold": None, "medianGold": None, "q75Gold": None, "sampleCount": 0}
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
            "positiveEngravings": _stone_option_names(row),
        })
    return sample


def _summary_base(stone: AbilityStoneSummary | None, fallback_price_gold: float) -> dict[str, Any]:
    return {
        "version": VERSION,
        "source": "lostark_auction_api_ability_stone_same_positive_engravings",
        "targetStone": None if not stone else {
            "name": stone.name,
            "grade": stone.grade,
            "positive1": stone.positive_1_name,
            "positive2": stone.positive_2_name,
            "negative": stone.negative_name,
            "stoneType": stone.stone_type,
        },
        "fallbackPriceGold": _gold(float(fallback_price_gold)),
    }


def _fallback_summary(stone: AbilityStoneSummary | None, fallback_price_gold: float, reason: str, rows: list[dict[str, Any]] | None = None, payloads: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = rows or []
    payloads = payloads or []
    base = _summary_base(stone, fallback_price_gold)
    base.update({
        "status": "failed",
        "failureReason": reason,
        "unitPriceGold": _gold(float(fallback_price_gold)),
        "fallbackApplied": True,
        "unitPrice": _price_summary([]),
        "matchingMode": "fallback_default",
        "matchingConditions": None if not stone else {
            "categoryCode": ABILITY_STONE_CATEGORY_CODE,
            "grade": stone.grade or "고대",
            "tier": 4,
            "itemNameTried": bool(stone.name),
            "requiredPositiveEngravings": _target_positive_names(stone),
            "excludedPenaltyEngraving": stone.negative_name,
            "pageLimit": STONE_AUCTION_PAGE_LIMIT,
            "sort": "BUY_PRICE ASC",
            "strictPositiveEngravingVerification": True,
        },
        "debug": {
            "rawItemCount": len(rows),
            "matchedItemCount": 0,
            "requestPayloadSample": payloads[0] if payloads else None,
            "sampleRows": _debug_sample(rows, stone),
        },
        "basis": "Ability stone unit price uses only auction listings whose positive engravings match the character stone. Penalty engravings are ignored/excluded from matching.",
    })
    return base


def build_ability_stone_market_summary(character: CharacterSummary, fallback_price_gold: float = 5000.0) -> dict[str, Any]:
    stone = character.ability_stone
    if not stone:
        return _fallback_summary(None, fallback_price_gold, "ability stone not found")
    if not get_settings().lostark_api_key:
        return _fallback_summary(stone, fallback_price_gold, "missing lostark api key")

    client = LostArkClient()
    rows, payloads = _search_rows(client, stone, use_name=True)
    if not rows:
        rows, payloads = _search_rows(client, stone, use_name=False)

    matched_rows = [row for row in rows if _same_positive_engravings(row, stone)]
    prices = [price for price in (_auction_buy_price(row) for row in matched_rows) if price is not None]
    if not prices:
        return _fallback_summary(stone, fallback_price_gold, "no recent listings with the same positive engravings", rows, payloads)

    summary = _price_summary(prices)
    unit_price = summary.get("medianGold") or _gold(float(fallback_price_gold))
    base = _summary_base(stone, fallback_price_gold)
    base.update({
        "status": "ok",
        "failureReason": None,
        "unitPriceGold": unit_price,
        "fallbackApplied": False,
        "unitPrice": summary,
        "matchingMode": "same_positive_engravings_penalty_ignored",
        "matchingConditions": {
            "categoryCode": ABILITY_STONE_CATEGORY_CODE,
            "grade": stone.grade or "고대",
            "tier": 4,
            "itemNameTried": bool(stone.name),
            "requiredPositiveEngravings": _target_positive_names(stone),
            "excludedPenaltyEngraving": stone.negative_name,
            "pageLimit": STONE_AUCTION_PAGE_LIMIT,
            "sort": "BUY_PRICE ASC",
            "strictPositiveEngravingVerification": True,
        },
        "debug": {
            "rawItemCount": len(rows),
            "matchedItemCount": len(matched_rows),
            "requestPayloadSample": payloads[0] if payloads else None,
            "sampleRows": _debug_sample(rows, stone),
        },
        "basis": "Ability stone unit price uses the auction buy-price median for listings with the same two positive engravings as the character stone. Penalty engravings are not used for matching.",
    })
    return base


def stone_market_unit_price(summary: dict[str, Any] | None, fallback_price_gold: float = 5000.0) -> float:
    if isinstance(summary, dict):
        value = summary.get("unitPriceGold")
        try:
            if value is not None and float(value) > 0:
                return float(value)
        except Exception:
            pass
    return float(fallback_price_gold)
