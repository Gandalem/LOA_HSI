from __future__ import annotations

from typing import Any

from app.core.settings import get_settings
from app.models.schemas import AbilityStoneSummary, CharacterSummary
from app.services.lostark_client import LostArkClient

ABILITY_STONE_CATEGORY_CODE = 30000
STONE_AUCTION_PAGE_LIMIT = 20
VERSION = "v60.24-stone-positive-engraving-filter"


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


def _norm(text: Any) -> str:
    return str(text or "").replace(" ", "").replace("[", "").replace("]", "").lower()


def _auction_filter_candidates(auction_options: Any) -> list[dict[str, Any]]:
    if not isinstance(auction_options, dict):
        return []
    roots = [
        ("EtcOptions", "EtcOptions"),
        ("etcOptions", "EtcOptions"),
        ("SkillOptions", "SkillOptions"),
        ("skillOptions", "SkillOptions"),
    ]
    candidates: list[dict[str, Any]] = []
    for source_key, payload_key in roots:
        groups = auction_options.get(source_key)
        if not isinstance(groups, list):
            continue
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
                if second is None or not child_text:
                    continue
                candidates.append({
                    "payloadKey": payload_key,
                    "FirstOption": first,
                    "SecondOption": second,
                    "text": child_text,
                    "parentText": parent_text,
                })
    return candidates


def _find_engraving_filter(name: str, auction_options: Any) -> dict[str, Any] | None:
    target = _norm(name)
    if not target:
        return None
    scored: list[tuple[int, dict[str, Any]]] = []
    for candidate in _auction_filter_candidates(auction_options):
        text = _norm(candidate.get("text"))
        parent = _norm(candidate.get("parentText"))
        if text == target:
            score = 100
        elif target in text or text in target:
            score = 70
        else:
            continue
        if "각인" in parent or "engrave" in parent:
            score += 20
        scored.append((score, candidate))
    if not scored:
        return None
    best = sorted(scored, key=lambda row: row[0], reverse=True)[0][1]
    return {
        "payloadKey": best["payloadKey"],
        "FirstOption": best["FirstOption"],
        "SecondOption": best["SecondOption"],
        "MinValue": 0,
        "MaxValue": 0,
        "Text": best.get("text"),
        "ParentText": best.get("parentText"),
    }


def _resolve_engraving_filters(stone: AbilityStoneSummary | None, auction_options: Any) -> dict[str, Any]:
    resolved: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for name in _target_positive_names(stone):
        row = _find_engraving_filter(name, auction_options)
        if row:
            resolved.append(row)
        else:
            unresolved.append(name)
    payload: dict[str, list[dict[str, Any]]] = {"SkillOptions": [], "EtcOptions": []}
    for row in resolved:
        key = row.get("payloadKey") or "EtcOptions"
        payload.setdefault(str(key), []).append({
            "FirstOption": row["FirstOption"],
            "SecondOption": row["SecondOption"],
            "MinValue": row["MinValue"],
            "MaxValue": row["MaxValue"],
        })
    return {"resolved": resolved, "unresolved": unresolved, "payload": payload}


def _payload(stone: AbilityStoneSummary | None, page_no: int, use_name: bool, option_filters: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    grade = stone.grade if stone and stone.grade else "고대"
    name = str(stone.name or "").strip() if stone else ""
    filters = option_filters or {}
    return {
        "ItemLevelMin": None,
        "ItemLevelMax": None,
        "ItemGradeQuality": None,
        "ItemUpgradeLevel": None,
        "ItemTradeAllowCount": None,
        "SkillOptions": filters.get("SkillOptions") or [],
        "EtcOptions": filters.get("EtcOptions") or [],
        "Sort": "BUY_PRICE",
        "CategoryCode": ABILITY_STONE_CATEGORY_CODE,
        "CharacterClass": None,
        "ItemTier": 4,
        "ItemGrade": grade,
        "ItemName": name if use_name and name else None,
        "PageNo": page_no,
        "SortCondition": "ASC",
    }


def _search_rows(client: LostArkClient, stone: AbilityStoneSummary | None, use_name: bool, option_filters: dict[str, list[dict[str, Any]]] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    payloads: list[dict[str, Any]] = []
    for page_no in range(1, STONE_AUCTION_PAGE_LIMIT + 1):
        payload = _payload(stone, page_no, use_name, option_filters)
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


def _fallback_summary(stone: AbilityStoneSummary | None, fallback_price_gold: float, reason: str, rows: list[dict[str, Any]] | None = None, payloads: list[dict[str, Any]] | None = None, filter_debug: dict[str, Any] | None = None) -> dict[str, Any]:
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
            "auctionEngravingFilter": filter_debug,
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
    auction_options = client.get_auction_options(optional=True)
    filter_debug = _resolve_engraving_filters(stone, auction_options)
    option_filters = filter_debug.get("payload") if not filter_debug.get("unresolved") else None

    rows: list[dict[str, Any]] = []
    payloads: list[dict[str, Any]] = []
    if option_filters and (option_filters.get("SkillOptions") or option_filters.get("EtcOptions")):
        rows, payloads = _search_rows(client, stone, use_name=True, option_filters=option_filters)

    if not rows:
        rows, payloads = _search_rows(client, stone, use_name=True)
        if not rows:
            rows, payloads = _search_rows(client, stone, use_name=False)

    matched_rows = [row for row in rows if _same_positive_engravings(row, stone)]
    prices = [price for price in (_auction_buy_price(row) for row in matched_rows) if price is not None]
    if not prices:
        return _fallback_summary(stone, fallback_price_gold, "no recent listings with the same positive engravings", rows, payloads, filter_debug)

    summary = _price_summary(prices)
    unit_price = summary.get("medianGold") or _gold(float(fallback_price_gold))
    base = _summary_base(stone, fallback_price_gold)
    base.update({
        "status": "ok",
        "failureReason": None,
        "unitPriceGold": unit_price,
        "fallbackApplied": False,
        "unitPrice": summary,
        "matchingMode": "same_positive_engravings_api_filter" if option_filters else "same_positive_engravings_post_filter",
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
            "auctionEngravingFilter": filter_debug,
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
