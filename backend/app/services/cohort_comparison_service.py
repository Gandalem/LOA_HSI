from __future__ import annotations

from dataclasses import dataclass
import time
from pathlib import Path
from typing import Any

import duckdb

from app.core.settings import get_settings


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _item_level_band(item_level: float, width: int) -> tuple[int, int]:
    base = int(item_level // width) * width
    return base, base + width - 1


def _percentile_rank(values: list[float], current: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    count = sum(1 for value in ordered if value <= current)
    return round((count / len(ordered)) * 100.0, 1)


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    index = (len(ordered) - 1) * q
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    if low == high:
        return float(ordered[low])
    ratio = index - low
    return float(ordered[low] + (ordered[high] - ordered[low]) * ratio)


def _distribution_summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "sampleCount": 0,
            "avg": None,
            "p50": None,
            "p75": None,
            "p90": None,
        }
    return {
        "sampleCount": len(values),
        "avg": round(sum(values) / len(values), 3),
        "p50": round(_quantile(values, 0.50) or 0.0, 3),
        "p75": round(_quantile(values, 0.75) or 0.0, 3),
        "p90": round(_quantile(values, 0.90) or 0.0, 3),
    }


def _verdict(percentile: float | None) -> str:
    if percentile is None:
        return "unavailable"
    if percentile >= 95:
        return "much_harder_than_peers"
    if percentile >= 80:
        return "harder_than_peers"
    if percentile <= 5:
        return "much_easier_than_peers"
    if percentile <= 20:
        return "easier_than_peers"
    return "similar_to_peers"


def _step_label(step: "CohortStep", item_level_band: str | None, sample_count: int) -> str:
    role_text = "같은 역할, " if step.require_role else ""
    band_text = f"{item_level_band} " if item_level_band else ""
    base = f"같은 직업, {role_text}{band_text}구간"
    if step.item_level_width is None:
        base = "같은 직업 전체 구간"
    return f"{base} 표본 {sample_count}명"


def _comparison_basis(step: "CohortStep") -> str:
    if step.require_role and step.item_level_width == 20:
        return "strict"
    if step.require_role and step.item_level_width == 40:
        return "balanced"
    if not step.require_role and step.item_level_width is not None:
        return "relaxed"
    return "broad"


@dataclass(frozen=True)
class CohortStep:
    name: str
    item_level_width: int | None
    require_role: bool


class CohortComparisonService:
    _dataset_cache: dict[str, Any] | None = None
    _dataset_cache_at: float = 0.0
    _dataset_cache_ttl_seconds: float = 60.0

    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.parquet_root = settings.data_dir / "parquet"
        self.processed_root = settings.data_dir / "processed"
        self.raw_root = settings.data_dir / "raw"
        self.character_pattern = self._glob("character_comparisons")
        self.module_pattern = self._glob("module_summaries")
        self.has_character_dataset = self._has_parquet("character_comparisons")
        self.has_module_dataset = self._has_parquet("module_summaries")
        self.normalized_character_path = self.parquet_root / "armory_normalized" / "character_snapshots.parquet"
        self.seed_canonical_path = self.processed_root / "loawa" / "loawa_seed_canonical.ndjson"
        self.raw_character_dir = self.raw_root / "characters"

    def compare(
        self,
        *,
        class_name: str,
        class_preset_role: str | None,
        item_avg_level: float | None,
        current_metrics: dict[str, float | None],
        min_sample_count: int = 30,
    ) -> dict[str, Any]:
        if not class_name or item_avg_level is None:
            return {
                "available": False,
                "reason": "missing_character_context",
            }
        if not self.has_character_dataset:
            return {
                "available": False,
                "reason": "no_comparison_dataset",
            }

        steps = [
            CohortStep("same_class_role_itemlevel_20", 20, True),
            CohortStep("same_class_role_itemlevel_40", 40, True),
            CohortStep("same_class_itemlevel_20", 20, False),
            CohortStep("same_class_itemlevel_40", 40, False),
            CohortStep("same_class_any_itemlevel", None, False),
        ]

        selected = None
        for step in steps:
            cohort = self._load_cohort(
                class_name=class_name,
                class_preset_role=class_preset_role,
                item_avg_level=item_avg_level,
                step=step,
            )
            if cohort["sampleCount"] >= min_sample_count:
                selected = cohort
                break
            if selected is None or cohort["sampleCount"] > selected["sampleCount"]:
                selected = cohort

        if not selected or selected["sampleCount"] <= 0:
            return {
                "available": False,
                "reason": "empty_cohort",
            }

        metrics: dict[str, Any] = {}
        for metric_name, current_value in current_metrics.items():
            values = selected["metricValues"].get(metric_name) or []
            if current_value is None or not values:
                metrics[metric_name] = {
                    "available": False,
                    "currentValue": current_value,
                    "distribution": _distribution_summary(values),
                    "percentile": None,
                    "verdict": "unavailable",
                }
                continue
            percentile = _percentile_rank(values, current_value)
            metrics[metric_name] = {
                "available": True,
                "currentValue": current_value,
                "distribution": _distribution_summary(values),
                "percentile": percentile,
                "verdict": _verdict(percentile),
            }

        return {
            "available": True,
            "cohort": {
                "className": class_name,
                "classPresetRole": selected["classPresetRole"],
                "sampleCount": selected["sampleCount"],
                "strategy": selected["strategy"],
                "strategyLabel": selected["strategyLabel"],
                "comparisonBasis": selected["comparisonBasis"],
                "itemLevelBand": selected["itemLevelBand"],
                "itemLevelWidth": selected["itemLevelWidth"],
            },
            "dataset": self.dataset_status(),
            "metrics": metrics,
        }

    def dataset_status(self, force_refresh: bool = False) -> dict[str, Any]:
        now = time.time()
        cached = self.__class__._dataset_cache
        if (
            not force_refresh
            and cached is not None
            and (now - self.__class__._dataset_cache_at) < self.__class__._dataset_cache_ttl_seconds
        ):
            return cached

        status = {
            "seedCharacterCount": self._count_ndjson_lines(self.seed_canonical_path),
            "rawArmoryBundleCount": self._count_raw_armory_bundles(),
            "normalizedCharacterCount": self._count_parquet_rows(self.normalized_character_path),
            "comparisonCharacterRows": self._count_parquet_pattern_rows(self.character_pattern),
            "comparisonDistinctCharacters": self._count_distinct_characters(self.character_pattern),
            "comparisonRunCount": self._count_parquet_pattern_rows(self._glob("comparison_runs")),
        }
        self.__class__._dataset_cache = status
        self.__class__._dataset_cache_at = now
        return status

    def _load_cohort(
        self,
        *,
        class_name: str,
        class_preset_role: str | None,
        item_avg_level: float,
        step: CohortStep,
    ) -> dict[str, Any]:
        query_filters = ["class_name = ?"]
        params: list[Any] = [class_name]
        role_value = class_preset_role if step.require_role else None
        if step.require_role and class_preset_role:
            query_filters.append("COALESCE(class_preset_role, '') = ?")
            params.append(class_preset_role)
        elif step.require_role:
            query_filters.append("COALESCE(class_preset_role, '') = ''")

        item_level_band = None
        if step.item_level_width:
            band_start, band_end = _item_level_band(item_avg_level, step.item_level_width)
            item_level_band = f"{band_start}-{band_end}"
            query_filters.append("item_avg_level >= ?")
            query_filters.append("item_avg_level < ?")
            params.extend([float(band_start), float(band_end + 1)])

        where_clause = " AND ".join(query_filters)
        chars_sql = (
            "SELECT run_id, character_name, COALESCE(server_name, '') AS server_name, "
            "market_reproduction_gold, stone_expected_gold, "
            "official_accessory_most_difficult_expected_attempts, "
            "official_bracelet_random_expected_attempts "
            f"FROM read_parquet('{self.character_pattern}', union_by_name=true) "
            f"WHERE {where_clause}"
        )
        with duckdb.connect(":memory:") as con:
            char_rows = con.execute(
                f"""
                SELECT
                    market_reproduction_gold,
                    stone_expected_gold,
                    official_accessory_most_difficult_expected_attempts,
                    official_bracelet_random_expected_attempts
                FROM ({chars_sql}) cohort_chars
                """,
                params,
            ).fetchall()
            if self.has_module_dataset:
                equipment_sql = (
                    "SELECT m.avg_gold "
                    f"FROM read_parquet('{self.module_pattern}', union_by_name=true) m "
                    f"JOIN ({chars_sql}) c "
                    "ON m.run_id = c.run_id "
                    "AND m.character_name = c.character_name "
                    "AND COALESCE(m.server_name, '') = c.server_name "
                    "WHERE m.module = 'equipment' "
                    "AND m.avg_gold IS NOT NULL"
                )
                totals_sql = (
                    "SELECT m.avg_gold "
                    f"FROM read_parquet('{self.module_pattern}', union_by_name=true) m "
                    f"JOIN ({chars_sql}) c "
                    "ON m.run_id = c.run_id "
                    "AND m.character_name = c.character_name "
                    "AND COALESCE(m.server_name, '') = c.server_name "
                    "WHERE m.module = 'total' "
                    "AND m.avg_gold IS NOT NULL"
                )
                equipment_rows = con.execute(equipment_sql, params).fetchall()
                total_rows = con.execute(totals_sql, params).fetchall()
            else:
                equipment_rows = []
                total_rows = []
            sample_count = int(
                con.execute(
                    f"SELECT COUNT(*) FROM ({chars_sql}) cohort_chars",
                    params,
                ).fetchone()[0]
            )

        metric_values = {
            "equipmentAvgGold": [
                value for value in (_safe_float(row[0]) for row in equipment_rows) if value is not None
            ],
            "marketReproductionGold": [
                value for value in (_safe_float(row[0]) for row in char_rows) if value is not None
            ],
            "stoneExpectedGold": [
                value for value in (_safe_float(row[1]) for row in char_rows) if value is not None
            ],
            "accessoryExpectedAttempts": [
                value for value in (_safe_float(row[2]) for row in char_rows) if value is not None
            ],
            "braceletExpectedAttempts": [
                value for value in (_safe_float(row[3]) for row in char_rows) if value is not None
            ],
            "totalSimulationAvgGold": [
                value for value in (_safe_float(row[0]) for row in total_rows) if value is not None
            ],
        }
        return {
            "strategy": step.name,
            "strategyLabel": _step_label(step, item_level_band, sample_count),
            "comparisonBasis": _comparison_basis(step),
            "classPresetRole": role_value,
            "itemLevelBand": item_level_band,
            "itemLevelWidth": step.item_level_width,
            "sampleCount": sample_count,
            "metricValues": metric_values,
        }

    def _has_parquet(self, table: str) -> bool:
        table_dir = self.parquet_root / table
        return table_dir.exists() and any(table_dir.glob("**/*.parquet"))

    def _glob(self, table: str) -> str:
        return str((self.parquet_root / table / "**" / "*.parquet")).replace("\\", "/").replace("'", "''")

    def _count_ndjson_lines(self, path: Path) -> int:
        if not path.exists():
            return 0
        count = 0
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    count += 1
        return count

    def _count_raw_armory_bundles(self) -> int:
        if not self.raw_character_dir.exists():
            return 0
        return sum(1 for _ in self.raw_character_dir.glob("*_armory_bundle_v1.json"))

    def _count_parquet_rows(self, path: Path) -> int:
        if not path.exists():
            return 0
        try:
            with duckdb.connect(":memory:") as con:
                return int(con.execute("SELECT COUNT(*) FROM read_parquet(?)", [str(path)]).fetchone()[0])
        except Exception:
            return 0

    def _count_parquet_pattern_rows(self, pattern: str) -> int:
        try:
            with duckdb.connect(":memory:") as con:
                return int(con.execute(f"SELECT COUNT(*) FROM read_parquet('{pattern}', union_by_name=true)").fetchone()[0])
        except Exception:
            return 0

    def _count_distinct_characters(self, pattern: str) -> int:
        try:
            with duckdb.connect(":memory:") as con:
                return int(
                    con.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM (
                            SELECT DISTINCT character_name, COALESCE(server_name, '') AS server_name
                            FROM read_parquet('{pattern}', union_by_name=true)
                        )
                        """
                    ).fetchone()[0]
                )
        except Exception:
            return 0
