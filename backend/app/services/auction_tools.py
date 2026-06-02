from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app.schemas import AuctionItemView


def _walk(obj: Any) -> Iterable[Any]:
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def get_items_list(data: Any) -> List[Dict[str, Any]]:
    """로아 경매장 응답에서 Items 배열을 유연하게 찾습니다."""
    if isinstance(data, dict):
        for key in ("Items", "items", "Data", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
        for value in data.values():
            found = get_items_list(value)
            if found:
                return found
    elif isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def get_total_count(data: Any) -> Optional[int]:
    if isinstance(data, dict):
        for key in ("TotalCount", "totalCount", "total_count"):
            value = data.get(key)
            if isinstance(value, int):
                return value
    return None


def _number(item: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = item.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _text(item: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str):
            return value
    return None


def _option_strings(item: Dict[str, Any]) -> List[str]:
    values: List[str] = []
    for obj in _walk(item):
        if not isinstance(obj, dict):
            continue
        # LostArk option objects often include OptionName/Value style fields.
        name = _text(obj, "OptionName", "Name", "Type", "StatType")
        value = obj.get("Value") or obj.get("MinValue") or obj.get("MaxValue")
        if name and value is not None:
            values.append(f"{name}: {value}")
    # 중복 제거, 너무 길지 않게 제한
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
        if len(result) >= 8:
            break
    return result


def item_to_view(item: Dict[str, Any]) -> AuctionItemView:
    return AuctionItemView(
        item_name=_text(item, "Name", "ItemName", "name", "itemName"),
        grade=_text(item, "Grade", "ItemGrade", "grade", "itemGrade"),
        tier=int(_number(item, "Tier", "ItemTier") or 0) or None,
        quality=int(_number(item, "GradeQuality", "ItemGradeQuality", "Quality") or 0) or None,
        buy_price=_number(item, "BuyPrice", "buyPrice"),
        bid_price=_number(item, "BidPrice", "bidPrice"),
        start_price=_number(item, "StartPrice", "startPrice"),
        end_date=_text(item, "EndDate", "endDate", "AuctionEndDate"),
        options=_option_strings(item),
        raw=item,
    )


def summarize_auction_items(data: Any, top_n: int = 10) -> List[AuctionItemView]:
    items = get_items_list(data)
    views = [item_to_view(item) for item in items]
    views.sort(key=lambda x: x.buy_price or x.bid_price or x.start_price or 10**18)
    return views[:top_n]


def auction_price(data: Any, mode: str = "min_buy_price", top_n: int = 5) -> Optional[float]:
    views = summarize_auction_items(data, top_n=max(top_n, 1))
    prices = [v.buy_price for v in views if isinstance(v.buy_price, (int, float)) and v.buy_price > 0]
    if not prices:
        prices = [v.bid_price for v in views if isinstance(v.bid_price, (int, float)) and v.bid_price > 0]
    if not prices:
        prices = [v.start_price for v in views if isinstance(v.start_price, (int, float)) and v.start_price > 0]
    if not prices:
        return None
    if mode == "avg_top_n":
        prices = prices[:top_n]
        return sum(prices) / len(prices)
    return min(prices)


def default_auction_payload(
    *,
    category_code: int,
    item_name: str = "",
    item_grade: str = "",
    item_tier: int = 4,
    page_no: int = 1,
    sort: str = "BUY_PRICE",
    sort_condition: str = "ASC",
    item_grade_quality: Optional[int] = None,
    character_class: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "CategoryCode": category_code,
        "ItemName": item_name,
        "ItemGrade": item_grade,
        "ItemTier": item_tier,
        "PageNo": page_no,
        "Sort": sort,
        "SortCondition": sort_condition,
    }
    if item_grade_quality is not None:
        payload["ItemGradeQuality"] = item_grade_quality
    if character_class:
        payload["CharacterClass"] = character_class
    if extra:
        payload.update(extra)
    # LostArk API accepts SkillOptions/EtcOptions for detailed searches. The frontend
    # sends those through the raw JSON editor because class/build conditions differ a lot.
    return payload
