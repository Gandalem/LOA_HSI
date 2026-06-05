from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from app.core.settings import get_settings
from app.models.schemas import CharacterSummary, ModuleCompareResult
from app.services.percentile import compare_user_cost, summarize_distribution

MODULE_COLUMNS = {
    "equipment": "equipment_gold",
    "abilityStone": "ability_stone_gold",
    "accessory": "accessory_gold",
    "total": "total_gold",
}


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def character_fingerprint(character: CharacterSummary) -> dict[str, Any]:
    return {
        "character": character.character_name,
        "server": character.server_name,
        "class": character.class_name,
        "itemAvgLevel": character.item_avg_level,
        "equipment": [
            {
                "slot": x.slot,
                "name": x.name,
                "grade": x.grade,
                "item_level": x.item_level,
                "honing": x.honing_level,
                "quality": x.quality,
            }
            for x in character.equipment
        ],
        "stone": character.ability_stone.model_dump() if character.ability_stone else None,
        "accessories": [
            {
                "slot": x.slot,
                "name": x.name,
                "grade": x.grade,
                "quality": x.quality,
            }
            for x in character.accessories
        ],
    }


def make_cache_key(character: CharacterSummary, compare_modules: list[str], simulation_count: int, seed: int | None, model_version: str = "v21", price_fingerprint: str | None = None) -> str:
    payload = {
        "modelVersion": model_version,
        "character": character_fingerprint(character),
        "modules": sorted(compare_modules),
        "simulationCount": simulation_count,
        "seed": seed,
        "priceFingerprint": price_fingerprint or "default-material-prices",
    }
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


class SimulationStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.db_dir = self.settings.data_dir / "db"
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.db_dir / "loa_hsi.duckdb"
        self._init_db()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.db_path))

    def _init_db(self) -> None:
        con = self._connect()
        try:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS simulation_runs (
                    cache_key VARCHAR PRIMARY KEY,
                    character_name VARCHAR,
                    modules_json VARCHAR,
                    simulation_count INTEGER,
                    seed INTEGER,
                    created_at TIMESTAMP,
                    model_version VARCHAR
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS simulation_rows (
                    cache_key VARCHAR,
                    row_index INTEGER,
                    equipment_gold DOUBLE,
                    ability_stone_gold DOUBLE,
                    accessory_gold DOUBLE,
                    total_gold DOUBLE
                )
                """
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_sim_rows_cache ON simulation_rows(cache_key)")
        finally:
            con.close()

    def exists(self, cache_key: str) -> bool:
        con = self._connect()
        try:
            row = con.execute("SELECT 1 FROM simulation_runs WHERE cache_key = ? LIMIT 1", [cache_key]).fetchone()
            return row is not None
        finally:
            con.close()

    def save(self, cache_key: str, character_name: str, modules: list[str], simulation_count: int, seed: int | None, module_values: dict[str, np.ndarray]) -> None:
        if self.exists(cache_key):
            return

        n = simulation_count
        df = pd.DataFrame({
            "cache_key": [cache_key] * n,
            "row_index": np.arange(n, dtype=np.int64),
            "equipment_gold": module_values.get("equipment", np.zeros(n, dtype=np.float64)),
            "ability_stone_gold": module_values.get("abilityStone", np.zeros(n, dtype=np.float64)),
            "accessory_gold": module_values.get("accessory", np.zeros(n, dtype=np.float64)),
        })
        df["total_gold"] = df["equipment_gold"] + df["ability_stone_gold"] + df["accessory_gold"]

        con = self._connect()
        try:
            con.execute("BEGIN TRANSACTION")
            con.execute(
                "INSERT INTO simulation_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    cache_key,
                    character_name,
                    stable_json(modules),
                    simulation_count,
                    seed,
                    datetime.now(timezone.utc).replace(tzinfo=None),
                    "v26",
                ],
            )
            con.register("rows_df", df)
            con.execute("INSERT INTO simulation_rows SELECT * FROM rows_df")
            con.unregister("rows_df")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def _fetch_values(self, cache_key: str, module: str) -> np.ndarray:
        col = MODULE_COLUMNS[module]
        con = self._connect()
        try:
            df = con.execute(f"SELECT {col} AS value FROM simulation_rows WHERE cache_key = ?", [cache_key]).fetchdf()
            return df["value"].to_numpy(dtype=np.float64)
        finally:
            con.close()

    def build_module_result(self, cache_key: str, module: str, actual: float, krw_per_gold: float) -> ModuleCompareResult:
        values = self._fetch_values(cache_key, module)
        return ModuleCompareResult(
            module=module,
            summary=summarize_distribution(values, krw_per_gold),
            user=compare_user_cost(values, actual, krw_per_gold),
        )

    def artifact_paths(self, cache_key: str) -> dict[str, str]:
        return {
            "duckdb": str(self.db_path),
            "cacheKey": cache_key,
            "table": "simulation_rows",
        }
