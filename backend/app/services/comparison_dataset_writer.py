from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from app.core.settings import get_settings

COMPARISON_TABLES = [
    "comparison_runs",
    "character_comparisons",
    "module_summaries",
    "comparison_failures",
]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


class ComparisonDatasetWriter:
    """Append-only batch comparison dataset persisted as Parquet + DuckDB views."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.parquet_root = self.settings.data_dir / "parquet"
        self.db_path = self.settings.data_dir / "db" / "loa_hsi.duckdb"
        self.parquet_root.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def write_run(
        self,
        run_row: dict[str, Any],
        character_rows: list[dict[str, Any]],
        module_rows: list[dict[str, Any]],
        failure_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        finished_at = self._parse_datetime(run_row.get("finished_at")) or _now_utc()
        date_key = finished_at.date().isoformat()
        run_id = str(run_row["run_id"])

        written: dict[str, str] = {}
        row_counts = {
            "comparison_runs": 1,
            "character_comparisons": len(character_rows),
            "module_summaries": len(module_rows),
            "comparison_failures": len(failure_rows),
        }

        table_rows = {
            "comparison_runs": [run_row],
            "character_comparisons": character_rows,
            "module_summaries": module_rows,
            "comparison_failures": failure_rows,
        }
        for table, rows in table_rows.items():
            if not rows:
                continue
            path = self._write_table(table, date_key, run_id, rows)
            written[table] = str(path)

        result = {
            "runId": run_id,
            "date": date_key,
            "writtenTables": written,
            "rowCounts": row_counts,
        }
        try:
            result["views"] = self.ensure_views()
            result["viewRefreshStatus"] = "ok"
        except Exception as exc:
            result["views"] = {}
            result["viewRefreshStatus"] = "failed"
            result["viewRefreshError"] = str(exc)
        return result

    def ensure_views(self) -> dict[str, str]:
        created: dict[str, str] = {}
        with duckdb.connect(str(self.db_path)) as con:
            for table in COMPARISON_TABLES:
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

    def _write_table(
        self,
        table: str,
        date_key: str,
        run_id: str,
        rows: list[dict[str, Any]],
    ) -> Path:
        out_dir = self.parquet_root / table / f"date={date_key}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{run_id}.parquet"
        pd.DataFrame(rows).to_parquet(out_path, index=False)
        return out_path

    def _parse_datetime(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None

    def _has_parquet(self, table: str) -> bool:
        table_dir = self.parquet_root / table
        return table_dir.exists() and any(table_dir.glob("**/*.parquet"))

    def _duckdb_glob(self, table: str) -> str:
        pattern = self.parquet_root / table / "**" / "*.parquet"
        return str(pattern).replace("\\", "/").replace("'", "''")
