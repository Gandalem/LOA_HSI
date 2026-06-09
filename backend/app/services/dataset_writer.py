from __future__ import annotations

import json
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from app.core.settings import get_settings
from app.models.schemas import CharacterSummary, EquipmentItem


DATASET_TABLES = [
    "character_snapshots",
    "equipment_items",
    "accessory_effects",
    "bracelet_effects",
    "ability_stones",
    "memory_inputs",
]


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


class DatasetWriter:
    """Persist report-time character snapshots into local Parquet + DuckDB views.

    Docker maps the host project data directory to /app/data, so files written here
    appear on Windows under D:\\LOA-HSI\\data when the default compose file is used.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.parquet_root = self.settings.data_dir / "parquet"
        self.db_path = self.settings.data_dir / "db" / "loa_hsi.duckdb"
        self.parquet_root.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def write_report_snapshot(
        self,
        character: CharacterSummary,
        expected_values: dict[str, Any],
        memory_hints: dict[str, Any] | None,
        model_version: str,
    ) -> dict[str, Any]:
        captured_at = _now_utc()
        date_key = captured_at.date().isoformat()
        snapshot_id = self._snapshot_id(character, captured_at)
        context = {
            "snapshot_id": snapshot_id,
            "captured_at": captured_at.isoformat(),
            "date_key": date_key,
            "model_version": model_version,
        }
        table_rows = {
            "character_snapshots": self._character_rows(character, expected_values, memory_hints, context),
            "equipment_items": self._equipment_rows(character, context),
            "accessory_effects": self._accessory_effect_rows(character, expected_values, context),
            "bracelet_effects": self._bracelet_effect_rows(character, expected_values, context),
            "ability_stones": self._ability_stone_rows(character, expected_values, context),
            "memory_inputs": self._memory_rows(character, expected_values, memory_hints or {}, context),
        }
        written: dict[str, str] = {}
        counts: dict[str, int] = {}
        for table, rows in table_rows.items():
            counts[table] = len(rows)
            if not rows:
                continue
            path = self._write_parquet(table, date_key, snapshot_id, rows)
            written[table] = str(path)
        views = self.ensure_views()
        return {
            "snapshotId": snapshot_id,
            "capturedAt": captured_at.isoformat(),
            "date": date_key,
            "writtenTables": written,
            "rowCounts": counts,
            "views": views,
        }

    def status(self) -> dict[str, Any]:
        self.ensure_views()
        table_status = {}
        total_size = 0
        for table in DATASET_TABLES:
            table_dir = self.parquet_root / table
            files = list(table_dir.glob("**/*.parquet")) if table_dir.exists() else []
            size = sum(path.stat().st_size for path in files if path.exists())
            total_size += size
            table_status[table] = {
                "files": len(files),
                "rows": self._row_count(table),
                "sizeBytes": size,
                "path": str(table_dir),
            }
        return {
            "parquetRoot": str(self.parquet_root),
            "duckdbPath": str(self.db_path),
            "totalSizeBytes": total_size,
            "tables": table_status,
        }

    def stats(self) -> dict[str, Any]:
        """Return compact dataset statistics for the v52 dashboard card."""
        status = self.status()
        summary = {
            "totalSizeBytes": status["totalSizeBytes"],
            "tables": status["tables"],
            "characterSnapshotCount": status["tables"].get("character_snapshots", {}).get("rows", 0),
            "equipmentItemCount": status["tables"].get("equipment_items", {}).get("rows", 0),
            "accessoryEffectCount": status["tables"].get("accessory_effects", {}).get("rows", 0),
            "braceletEffectCount": status["tables"].get("bracelet_effects", {}).get("rows", 0),
            "abilityStoneCount": status["tables"].get("ability_stones", {}).get("rows", 0),
            "memoryInputCount": status["tables"].get("memory_inputs", {}).get("rows", 0),
        }
        return {
            **summary,
            "recentSnapshots": self._query_rows(
                """
                SELECT snapshot_id, captured_at, character_name, server_name, class_name,
                       item_avg_level, preset_role, official_accessory_matched_effects,
                       official_accessory_unmatched_effects
                FROM v_character_snapshots
                ORDER BY captured_at DESC
                LIMIT 8
                """,
                required_view="v_character_snapshots",
            ),
            "classCounts": self._query_rows(
                """
                SELECT COALESCE(class_name, '알 수 없음') AS class_name, COUNT(*) AS snapshots
                FROM v_character_snapshots
                GROUP BY 1
                ORDER BY snapshots DESC, class_name ASC
                LIMIT 12
                """,
                required_view="v_character_snapshots",
            ),
            "stoneTypeCounts": self._query_rows(
                """
                SELECT COALESCE(stone_type, '알 수 없음') AS stone_type, COUNT(*) AS stones
                FROM v_ability_stones
                GROUP BY 1
                ORDER BY stones DESC, stone_type ASC
                LIMIT 12
                """,
                required_view="v_ability_stones",
            ),
            "accessoryMatching": self._query_one(
                """
                SELECT
                    SUM(CASE WHEN matched THEN 1 ELSE 0 END) AS matched_effects,
                    SUM(CASE WHEN matched THEN 0 ELSE 1 END) AS unmatched_effects,
                    COUNT(*) AS total_effects
                FROM v_accessory_effects
                """,
                required_view="v_accessory_effects",
            ),
        }

    def ensure_views(self) -> dict[str, str]:
        created: dict[str, str] = {}
        with duckdb.connect(str(self.db_path)) as con:
            for table in DATASET_TABLES:
                if not self._has_parquet(table):
                    created[table] = "skipped_no_files"
                    continue
                view_name = f"v_{table}"
                pattern = self._duckdb_glob(table)
                con.execute(
                    f"CREATE OR REPLACE VIEW {view_name} AS "
                    f"SELECT * FROM read_parquet('{pattern}', union_by_name=true)"
                )
                created[table] = view_name
        return created

    def _query_rows(self, query: str, required_view: str) -> list[dict[str, Any]]:
        try:
            with duckdb.connect(str(self.db_path)) as con:
                if not self._view_exists(con, required_view):
                    return []
                return con.execute(query).fetchdf().to_dict("records")
        except Exception:
            return []

    def _query_one(self, query: str, required_view: str) -> dict[str, Any]:
        rows = self._query_rows(query, required_view)
        return rows[0] if rows else {}

    def _view_exists(self, con: duckdb.DuckDBPyConnection, view_name: str) -> bool:
        result = con.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
            [view_name],
        ).fetchone()
        return bool(result and result[0])

    def _snapshot_id(self, character: CharacterSummary, captured_at: datetime) -> str:
        base = f"{character.server_name}:{character.character_name}:{captured_at.isoformat()}:{uuid.uuid4().hex}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:24]

    def _write_parquet(self, table: str, date_key: str, snapshot_id: str, rows: list[dict[str, Any]]) -> Path:
        out_dir = self.parquet_root / table / f"date={date_key}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{snapshot_id}.parquet"
        pd.DataFrame(rows).to_parquet(out_path, index=False)
        return out_path

    def _has_parquet(self, table: str) -> bool:
        table_dir = self.parquet_root / table
        return table_dir.exists() and any(table_dir.glob("**/*.parquet"))

    def _duckdb_glob(self, table: str) -> str:
        return str((self.parquet_root / table / "**" / "*.parquet")).replace("\\", "/").replace("'", "''")

    def _row_count(self, table: str) -> int:
        if not self._has_parquet(table):
            return 0
        pattern = self._duckdb_glob(table)
        try:
            with duckdb.connect(str(self.db_path)) as con:
                return int(con.execute(f"SELECT COUNT(*) FROM read_parquet('{pattern}', union_by_name=true)").fetchone()[0])
        except Exception:
            return 0

    def _base_row(self, character: CharacterSummary, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "snapshot_id": context["snapshot_id"],
            "captured_at": context["captured_at"],
            "date": context["date_key"],
            "model_version": context["model_version"],
            "character_name": character.character_name,
            "server_name": character.server_name,
            "class_name": character.class_name,
        }

    def _character_rows(
        self,
        character: CharacterSummary,
        expected_values: dict[str, Any],
        memory_hints: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        preset = character.class_engraving_preset or {}
        official_accessory = expected_values.get("officialAccessoryEffects") or {}
        row = self._base_row(character, context)
        row.update(
            {
                "item_avg_level": _safe_float(character.item_avg_level),
                "character_level": _safe_int(character.character_level),
                "raw_saved_path": character.raw_saved_path,
                "preset_role": preset.get("role"),
                "preset_engraving": preset.get("engravingName") or preset.get("engraving_name"),
                "preset_confidence": preset.get("confidence"),
                "equipment_count": len(character.equipment or []),
                "accessory_count": len(character.accessories or []),
                "official_accessory_matched_effects": _safe_int(official_accessory.get("matchedEffectCount")) or 0,
                "official_accessory_unmatched_effects": _safe_int(official_accessory.get("unmatchedEffectCount")) or 0,
                "memory_hints_json": _json_dumps(memory_hints or {}),
            }
        )
        return [row]

    def _equipment_rows(self, character: CharacterSummary, context: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for index, item in enumerate(character.equipment or []):
            row = self._base_row(character, context)
            row.update(
                {
                    "item_index": index,
                    "slot": item.slot,
                    "name": item.name,
                    "grade": item.grade,
                    "item_level": _safe_float(item.item_level),
                    "honing_level": _safe_int(item.honing_level),
                    "quality": _safe_int(item.quality),
                }
            )
            rows.append(row)
        return rows

    def _accessory_effect_rows(self, character: CharacterSummary, expected_values: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
        official_items = (expected_values.get("officialAccessoryEffects") or {}).get("items") or []
        rows = []
        for item_index, official_item in enumerate(official_items):
            matched = official_item.get("matchedEffects") or []
            unmatched = official_item.get("unmatchedEffects") or []
            for effect_index, effect in enumerate(matched):
                row = self._base_row(character, context)
                row.update(
                    {
                        "item_index": item_index,
                        "effect_index": effect_index,
                        "slot": official_item.get("slot"),
                        "accessory_name": official_item.get("name"),
                        "effect_text": effect.get("rawEffect"),
                        "matched": True,
                        "official_name": effect.get("officialName"),
                        "grade_label": effect.get("grade"),
                        "grade_rank": _safe_int(effect.get("gradeRank")),
                        "effect_value": _safe_float(effect.get("value")),
                        "display_probability": _safe_float(effect.get("displayProbability")),
                        "is_core": bool(effect.get("isCore")),
                        "is_secondary": bool(effect.get("isSecondary")),
                        "match_role": effect.get("matchRole"),
                        "item_expected_attempts": _safe_float(official_item.get("expectedAttempts")),
                        "item_combination_probability": _safe_float(official_item.get("combinationProbability")),
                        "target_basis": official_item.get("targetBasis"),
                    }
                )
                rows.append(row)
            for offset, effect_text in enumerate(unmatched):
                row = self._base_row(character, context)
                row.update(
                    {
                        "item_index": item_index,
                        "effect_index": len(matched) + offset,
                        "slot": official_item.get("slot"),
                        "accessory_name": official_item.get("name"),
                        "effect_text": effect_text,
                        "matched": False,
                        "official_name": None,
                        "grade_label": None,
                        "grade_rank": None,
                        "effect_value": None,
                        "display_probability": None,
                        "is_core": False,
                        "is_secondary": False,
                        "match_role": "unmatched",
                        "item_expected_attempts": _safe_float(official_item.get("expectedAttempts")),
                        "item_combination_probability": _safe_float(official_item.get("combinationProbability")),
                        "target_basis": official_item.get("targetBasis"),
                    }
                )
                rows.append(row)
        return rows

    def _bracelet_effect_rows(self, character: CharacterSummary, expected_values: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
        bracelet_item = next((x for x in character.accessories if x.slot == "팔찌"), None)
        if not bracelet_item:
            return []
        bracelet = expected_values.get("braceletT4") or {}
        buckets = {
            "valid": set(bracelet.get("currentValidEffects") or []),
            "secondary": set(bracelet.get("currentSecondaryEffects") or []),
            "conditional": set(bracelet.get("currentConditionalEffects") or []),
            "nonCore": set(bracelet.get("currentNonCoreEffects") or []),
        }
        rows = []
        for index, effect in enumerate(bracelet_item.bracelet_effects or []):
            bucket = next((name for name, values in buckets.items() if effect in values), "unknown")
            row = self._base_row(character, context)
            row.update(
                {
                    "effect_index": index,
                    "bracelet_name": bracelet_item.name,
                    "grade": bracelet_item.grade,
                    "quality": _safe_int(bracelet_item.quality),
                    "effect_text": effect,
                    "bucket": bucket,
                }
            )
            rows.append(row)
        return rows

    def _ability_stone_rows(self, character: CharacterSummary, expected_values: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
        stone = character.ability_stone
        if not stone:
            return []
        expected = expected_values.get("abilityStone") or {}
        row = self._base_row(character, context)
        row.update(
            {
                "stone_name": stone.name,
                "grade": stone.grade,
                "positive_1_name": stone.positive_1_name,
                "positive_1_points": _safe_int(stone.positive_1_points),
                "positive_2_name": stone.positive_2_name,
                "positive_2_points": _safe_int(stone.positive_2_points),
                "negative_name": stone.negative_name,
                "negative_points": _safe_int(stone.negative_points),
                "stone_type": stone.stone_type,
                "quality": _safe_int(stone.quality),
                "target": expected.get("target"),
                "success_count_target": expected.get("successCountTarget"),
                "success_probability_per_stone": _safe_float(expected.get("successProbabilityPerStone")),
                "expected_stones": _safe_float(expected.get("expectedStones")),
                "expected_gold": _safe_float(expected.get("expectedGold")),
            }
        )
        return [row]

    def _memory_rows(
        self,
        character: CharacterSummary,
        expected_values: dict[str, Any],
        memory_hints: dict[str, Any],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        row = self._base_row(character, context)
        row.update(
            {
                "stone_attempts": _safe_int(memory_hints.get("stoneAttempts")),
                "pity_records_json": _json_dumps(memory_hints.get("pityRecords") or []),
                "accessory_acquisitions_json": _json_dumps(memory_hints.get("accessoryAcquisitions") or {}),
                "bracelet_acquisition_json": _json_dumps(memory_hints.get("braceletAcquisition") or {}),
                "memory_hints_json": _json_dumps(memory_hints),
                "actual_cost_mode": expected_values.get("actualCostMode"),
            }
        )
        return [row]
