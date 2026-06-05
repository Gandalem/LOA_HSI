from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from app.core.settings import get_settings


LATEST_COLUMNS = [
    "material_key",
    "material_name",
    "search_name",
    "item_id",
    "raw_price_gold",
    "bundle_count",
    "unit_price_gold",
    "source",
    "raw_path",
    "note",
    "collected_at",
]

SNAPSHOT_COLUMNS = ["snapshot_id", "collected_at", *LATEST_COLUMNS[:-1]]


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _none_if_nan(value: Any) -> Any:
    try:
        # DuckDB/Pandas/NumPy 계열 NaN 방어
        if value != value:
            return None
    except Exception:
        pass
    return value


class MaterialPriceStore:
    """재련 재료 가격 스냅샷 저장소.

    v13 변경점:
    - 오래된 DuckDB 테이블 스키마가 남아 있어도 자동으로 material price 테이블만 재생성합니다.
    - latest 조회에서 pandas fetchdf를 쓰지 않아 pandas/NaT 변환 문제를 피합니다.
    - INSERT OR REPLACE 대신 DELETE + INSERT를 사용해 DuckDB 버전 차이를 줄입니다.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.db_dir = self.settings.data_dir / "db"
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir = self.settings.data_dir / "raw" / "markets"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.db_dir / "loa_hsi.duckdb"
        self._init_db()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.db_path))

    def _table_columns(self, con: duckdb.DuckDBPyConnection, table_name: str) -> list[str]:
        try:
            rows = con.execute(f"PRAGMA table_info('{table_name}')").fetchall()
            return [str(row[1]) for row in rows]
        except Exception:
            return []

    def _has_expected_schema(self, con: duckdb.DuckDBPyConnection) -> bool:
        latest = self._table_columns(con, "material_price_latest")
        snapshots = self._table_columns(con, "material_price_snapshots")
        return latest == LATEST_COLUMNS and snapshots == SNAPSHOT_COLUMNS

    def _create_tables(self, con: duckdb.DuckDBPyConnection) -> None:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS material_price_snapshots (
                snapshot_id VARCHAR,
                collected_at TIMESTAMP,
                material_key VARCHAR,
                material_name VARCHAR,
                search_name VARCHAR,
                item_id BIGINT,
                raw_price_gold DOUBLE,
                bundle_count DOUBLE,
                unit_price_gold DOUBLE,
                source VARCHAR,
                raw_path VARCHAR,
                note VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS material_price_latest (
                material_key VARCHAR,
                material_name VARCHAR,
                search_name VARCHAR,
                item_id BIGINT,
                raw_price_gold DOUBLE,
                bundle_count DOUBLE,
                unit_price_gold DOUBLE,
                source VARCHAR,
                raw_path VARCHAR,
                note VARCHAR,
                collected_at TIMESTAMP
            )
            """
        )

    def _init_db(self) -> None:
        con = self._connect()
        try:
            self._create_tables(con)
            if not self._has_expected_schema(con):
                # 오래된 개발 DB가 남아 있으면 material price 테이블만 재생성합니다.
                con.execute("DROP TABLE IF EXISTS material_price_snapshots")
                con.execute("DROP TABLE IF EXISTS material_price_latest")
                self._create_tables(con)
        finally:
            con.close()

    def save_raw(self, material_key: str, data: Any) -> str:
        ts = time.strftime("%Y%m%d_%H%M%S")
        safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in material_key)
        path = self.raw_dir / f"{ts}_{safe}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def upsert_price(self, row: dict[str, Any]) -> None:
        collected_at = row.get("collected_at") or datetime.now(timezone.utc).replace(tzinfo=None)
        snapshot_payload = {k: row.get(k) for k in ["material_key", "unit_price_gold", "source", "item_id", "search_name"]}
        snapshot_id = hashlib.sha256(stable_json({**snapshot_payload, "collected_at": str(collected_at)}).encode("utf-8")).hexdigest()

        latest_values = [
            row.get("material_key"),
            row.get("material_name"),
            row.get("search_name"),
            row.get("item_id"),
            row.get("raw_price_gold"),
            row.get("bundle_count"),
            row.get("unit_price_gold"),
            row.get("source"),
            row.get("raw_path"),
            row.get("note"),
            collected_at,
        ]
        snapshot_values = [snapshot_id, collected_at, *latest_values[:-1]]

        con = self._connect()
        try:
            con.execute(
                "INSERT INTO material_price_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                snapshot_values,
            )
            con.execute("DELETE FROM material_price_latest WHERE material_key = ?", [row.get("material_key")])
            con.execute(
                "INSERT INTO material_price_latest VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                latest_values,
            )
        finally:
            con.close()

    def latest_rows(self) -> list[dict[str, Any]]:
        con = self._connect()
        try:
            cursor = con.execute(
                """
                SELECT material_key, material_name, search_name, item_id, raw_price_gold,
                       bundle_count, unit_price_gold, source, raw_path, note, collected_at
                FROM material_price_latest
                ORDER BY material_key
                """
            )
            columns = [d[0] for d in cursor.description]
            rows = []
            for raw_row in cursor.fetchall():
                rows.append({columns[i]: _none_if_nan(raw_row[i]) for i in range(len(columns))})
            return rows
        finally:
            con.close()

    def latest_price_map(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for row in self.latest_rows():
            key = row.get("material_key")
            price = row.get("unit_price_gold")
            if key and price is not None:
                try:
                    result[str(key)] = float(price)
                except Exception:
                    pass
        return result

    def latest_fingerprint(self) -> str:
        rows = self.latest_rows()
        compact = [
            {
                "key": r.get("material_key"),
                "price": round(float(r.get("unit_price_gold") or 0), 8),
                "collected_at": str(r.get("collected_at")),
            }
            for r in rows
        ]
        if not compact:
            return "default-material-prices"
        return hashlib.sha256(stable_json(compact).encode("utf-8")).hexdigest()


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


def _extract_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        items = data.get("Items") or data.get("items")
        if isinstance(items, list):
            return [x for x in items if isinstance(x, dict)]
        return [data]
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _item_name(item: dict[str, Any]) -> str:
    for key in ["Name", "name", "ItemName", "itemName"]:
        value = item.get(key)
        if value:
            return str(value)
    return ""


def _name_score(item_name: str, preferred_names: list[str] | None) -> int:
    if not preferred_names:
        return 2
    normalized = item_name.replace(" ", "").lower()
    best = 5
    for raw in preferred_names:
        pref = str(raw or "").strip()
        if not pref:
            continue
        n_pref = pref.replace(" ", "").lower()
        if normalized == n_pref:
            best = min(best, 0)
        elif normalized.startswith(n_pref) or n_pref.startswith(normalized):
            best = min(best, 1)
        elif n_pref in normalized:
            best = min(best, 2)
    return best


def extract_market_price(data: Any, preferred_names: list[str] | None = None) -> tuple[float | None, float | None, int | None, str | None]:
    """Return raw_price, bundle_count, item_id, note.

    Lost Ark market responses often expose CurrentMinPrice as bundle price. The
    caller divides by BundleCount to convert it to the simulator's 1-item unit cost.
    Prefer exact/near item-name matches before falling back to the cheapest result,
    so a broad query such as `운명의 파편 주머니` does not accidentally choose an
    unrelated item.
    """
    items = _extract_items(data)
    if not items:
        return None, None, None, "응답에서 Items를 찾지 못했습니다."

    candidates: list[tuple[int, float, float, dict[str, Any]]] = []
    for item in items:
        price = _find_numeric(item, ["CurrentMinPrice", "currentMinPrice", "RecentPrice", "recentPrice", "YDayAvgPrice", "yDayAvgPrice"])
        if price is not None and price > 0:
            bundle = _find_numeric(item, ["BundleCount", "bundleCount"]) or 1.0
            unit_price = float(price) / max(float(bundle), 1.0)
            candidates.append((_name_score(_item_name(item), preferred_names), unit_price, price, item))
    if not candidates:
        return None, None, None, "가격 필드를 찾지 못했습니다."

    score, _unit_price, raw_price, item = sorted(candidates, key=lambda x: (x[0], x[1]))[0]
    bundle_count = _find_numeric(item, ["BundleCount", "bundleCount"]) or 1.0
    item_id = _find_numeric(item, ["Id", "ID", "id", "ItemId", "itemId"])
    note = None
    if score >= 3 and preferred_names:
        note = f"정확한 이름 매칭 실패. 검색어 {preferred_names[0]} 기준 최저가 후보를 사용했습니다."
    return raw_price, bundle_count, int(item_id) if item_id is not None else None, note
