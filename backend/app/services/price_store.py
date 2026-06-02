from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.config import PROCESSED_DIR, RAW_DIR


def utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_filename(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in value)


def save_raw_json(kind: str, key: str, data: Any) -> str:
    date_dir = RAW_DIR / kind / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)
    path = date_dir / f"{datetime.now(timezone.utc).strftime('%H%M%S')}_{safe_filename(key)}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _iter_values(obj: Any) -> Iterable[Any]:
    if isinstance(obj, dict):
        for value in obj.values():
            yield value
            yield from _iter_values(value)
    elif isinstance(obj, list):
        for item in obj:
            yield item
            yield from _iter_values(item)


def _first_number_by_keys(obj: Any, keys: List[str]) -> Optional[float]:
    """API 응답 구조가 조금 달라도 가격 후보를 찾기 위한 느슨한 추출기."""
    if isinstance(obj, dict):
        for key in keys:
            if key in obj and isinstance(obj[key], (int, float)):
                return float(obj[key])
        for value in obj.values():
            found = _first_number_by_keys(value, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        candidates: List[float] = []
        for item in obj:
            found = _first_number_by_keys(item, keys)
            if found is not None and found > 0:
                candidates.append(found)
        if candidates:
            return float(min(candidates))
    return None


def extract_market_price(data: Any) -> Optional[float]:
    # 마켓 응답에서 자주 쓰이는 가격 필드 후보를 우선 탐색합니다.
    return _first_number_by_keys(data, ["CurrentMinPrice", "RecentPrice", "YDayAvgPrice", "AvgPrice", "TradeRemainCount"])


def extract_auction_buy_price(data: Any) -> Optional[float]:
    # 경매장 응답에서 즉시 구매가 후보를 탐색합니다.
    # 더 정확한 추출은 auction_tools.auction_price를 사용합니다.
    return _first_number_by_keys(data, ["BuyPrice", "BidPrice", "StartPrice"])


def load_latest_prices() -> Dict[str, Any]:
    path = PROCESSED_DIR / "latest_prices.json"
    if not path.exists():
        return {"updated_at": None, "prices": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_latest_prices(prices: Dict[str, Dict[str, Any]]) -> str:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / "latest_prices.json"
    payload = {
        "updated_at": utc_ts(),
        "prices": prices,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def merge_latest_prices(new_prices: Dict[str, Dict[str, Any]]) -> str:
    current = load_latest_prices().get("prices", {})
    current.update(new_prices)
    return save_latest_prices(current)


def price_map_for_simulation() -> Dict[str, float]:
    payload = load_latest_prices()
    result: Dict[str, float] = {}
    for key, item in payload.get("prices", {}).items():
        price = item.get("price_gold")
        if isinstance(price, (int, float)):
            result[key] = float(price)
    return result
