from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

def load_backend_parsers():
    try:
        from app.services.character_parser import build_character_summary  # type: ignore
        from app.services.class_preset import resolve_class_engraving_preset  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        missing = getattr(exc, "name", None) or str(exc)
        raise SystemExit(
            "Missing Python dependency for backend parser: "
            f"{missing}. Install backend requirements first with "
            "`python -m pip install -r backend/requirements.txt`."
        ) from exc
    return build_character_summary, resolve_class_engraving_preset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize armory raw bundles into current datasets.")
    parser.add_argument(
        "--data-dir",
        default=str(ROOT / "data"),
        help="Data root. Default: ./data",
    )
    parser.add_argument(
        "--canonical",
        default=None,
        help="Canonical seed NDJSON path. Default: <data-dir>/processed/loawa/loawa_seed_canonical.ndjson",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Normalized dataset output root. Default: <data-dir>/processed/armory_normalized",
    )
    parser.add_argument(
        "--parquet-dir",
        default=None,
        help="Parquet output root. Default: <data-dir>/parquet/armory_normalized",
    )
    parser.add_argument(
        "--status",
        default="armory_ok",
        help="Comma-separated armory statuses to include. Default: armory_ok",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max character rows to normalize. 0 means all.",
    )
    parser.add_argument(
        "--source-field",
        default="armoryRawPath",
        choices=["armoryRawPath", "apiRawPath"],
        help="Canonical field that points to raw bundle file.",
    )
    parser.add_argument(
        "--skip-parquet",
        action="store_true",
        help="Write NDJSON only and skip Parquet output.",
    )
    return parser.parse_args()


def read_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"NDJSON not found: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_ndjson(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def try_write_parquet(path: Path, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "skipped_no_rows"
    try:
        import pandas as pd  # type: ignore
    except Exception as exc:  # pragma: no cover - environment dependent
        return f"skipped_missing_pandas:{exc}"

    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)
    return "written"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def snapshot_id_for(character_name: str, server_name: str | None, raw_path: str) -> str:
    key = f"{server_name or ''}:{character_name}:{raw_path}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:24]


def build_character_row(
    canonical_row: dict[str, Any],
    summary: Any,
    class_preset: dict[str, Any] | None,
    bundle: dict[str, Any],
    raw_path: str,
) -> dict[str, Any]:
    fetched_at = bundle.get("fetchedAt") or canonical_row.get("armoryLastCheckedAt") or canonical_row.get("apiLastCheckedAt")
    snapshot_id = snapshot_id_for(summary.character_name, summary.server_name, raw_path)
    return {
        "snapshot_id": snapshot_id,
        "character_name": summary.character_name,
        "server_name": summary.server_name,
        "class_name": summary.class_name,
        "character_level": summary.character_level,
        "item_avg_level": summary.item_avg_level,
        "equipment_count": len(summary.equipment or []),
        "accessory_count": len(summary.accessories or []),
        "warning_count": len(summary.warnings or []),
        "warnings_json": json.dumps(summary.warnings or [], ensure_ascii=False),
        "class_preset_role": (class_preset or {}).get("role"),
        "class_preset_engraving": (class_preset or {}).get("engravingName"),
        "class_preset_confidence": (class_preset or {}).get("confidence"),
        "class_preset_method": (class_preset or {}).get("detectionMethod"),
        "class_preset_score": (class_preset or {}).get("score"),
        "class_preset_json": json.dumps(class_preset or {}, ensure_ascii=False),
        "armory_status": canonical_row.get("armoryStatus"),
        "source_field": "armoryRawPath" if canonical_row.get("armoryRawPath") == raw_path else "apiRawPath",
        "source_raw_path": raw_path,
        "source_hrefs_json": json.dumps(canonical_row.get("hrefs") or [], ensure_ascii=False),
        "seed_seen_count": canonical_row.get("seenCount"),
        "seed_sources_json": json.dumps(canonical_row.get("seenSources") or [], ensure_ascii=False),
        "seed_first_seen_at": canonical_row.get("firstSeenAt"),
        "seed_last_seen_at": canonical_row.get("lastSeenAt"),
        "bundle_fetched_at": fetched_at,
        "normalized_at": now_iso(),
    }


def build_accessory_rows(
    snapshot_id: str,
    summary: Any,
    class_preset: dict[str, Any] | None,
    raw_path: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    accessory_rows: list[dict[str, Any]] = []
    accessory_effect_rows: list[dict[str, Any]] = []
    bracelet_rows: list[dict[str, Any]] = []
    bracelet_effect_rows: list[dict[str, Any]] = []

    accessory_index = 0
    bracelet_index = 0
    for item in summary.accessories or []:
        common = {
            "snapshot_id": snapshot_id,
            "character_name": summary.character_name,
            "server_name": summary.server_name,
            "class_name": summary.class_name,
            "class_preset_role": (class_preset or {}).get("role"),
            "source_raw_path": raw_path,
            "slot": item.slot,
            "name": item.name,
            "grade": item.grade,
            "quality": item.quality,
            "item_level": item.item_level,
            "polish_level": item.polish_level,
            "enlightenment_points": item.enlightenment_points,
            "raw_tooltip_excerpt": item.raw_tooltip_excerpt,
        }
        if item.slot == "팔찌":
            row_id = f"{snapshot_id}:bracelet:{bracelet_index}"
            effects = [str(x) for x in (item.bracelet_effects or [])]
            bracelet_rows.append(
                {
                    **common,
                    "bracelet_index": bracelet_index,
                    "bracelet_row_id": row_id,
                    "effect_count": len(effects),
                    "effects_json": json.dumps(effects, ensure_ascii=False),
                }
            )
            for effect_index, effect in enumerate(effects):
                bracelet_effect_rows.append(
                    {
                        "snapshot_id": snapshot_id,
                        "bracelet_row_id": row_id,
                        "bracelet_index": bracelet_index,
                        "effect_index": effect_index,
                        "character_name": summary.character_name,
                        "server_name": summary.server_name,
                        "class_name": summary.class_name,
                        "class_preset_role": (class_preset or {}).get("role"),
                        "slot": item.slot,
                        "bracelet_name": item.name,
                        "bracelet_grade": item.grade,
                        "bracelet_quality": item.quality,
                        "effect_text": effect,
                        "source_raw_path": raw_path,
                    }
                )
            bracelet_index += 1
            continue

        row_id = f"{snapshot_id}:accessory:{accessory_index}"
        effects = [str(x) for x in (item.accessory_effects or [])]
        accessory_rows.append(
            {
                **common,
                "accessory_index": accessory_index,
                "accessory_row_id": row_id,
                "effect_count": len(effects),
                "effects_json": json.dumps(effects, ensure_ascii=False),
            }
        )
        for effect_index, effect in enumerate(effects):
            accessory_effect_rows.append(
                {
                    "snapshot_id": snapshot_id,
                    "accessory_row_id": row_id,
                    "accessory_index": accessory_index,
                    "effect_index": effect_index,
                    "character_name": summary.character_name,
                    "server_name": summary.server_name,
                    "class_name": summary.class_name,
                    "class_preset_role": (class_preset or {}).get("role"),
                    "slot": item.slot,
                    "accessory_name": item.name,
                    "accessory_grade": item.grade,
                    "accessory_quality": item.quality,
                    "effect_text": effect,
                    "source_raw_path": raw_path,
                }
            )
        accessory_index += 1

    return accessory_rows, accessory_effect_rows, bracelet_rows, bracelet_effect_rows


def build_stone_row(
    snapshot_id: str,
    summary: Any,
    class_preset: dict[str, Any] | None,
    raw_path: str,
) -> dict[str, Any] | None:
    stone = summary.ability_stone
    if not stone:
        return None
    return {
        "snapshot_id": snapshot_id,
        "character_name": summary.character_name,
        "server_name": summary.server_name,
        "class_name": summary.class_name,
        "class_preset_role": (class_preset or {}).get("role"),
        "name": stone.name,
        "grade": stone.grade,
        "quality": stone.quality,
        "stone_type": stone.stone_type,
        "positive_1_name": stone.positive_1_name,
        "positive_1_points": stone.positive_1_points,
        "positive_2_name": stone.positive_2_name,
        "positive_2_points": stone.positive_2_points,
        "negative_name": stone.negative_name,
        "negative_points": stone.negative_points,
        "raw_tooltip_excerpt": stone.raw_tooltip_excerpt,
        "source_raw_path": raw_path,
    }


def main() -> None:
    args = parse_args()
    build_character_summary, resolve_class_engraving_preset = load_backend_parsers()
    data_dir = Path(args.data_dir).resolve()
    canonical_path = Path(args.canonical).resolve() if args.canonical else data_dir / "processed" / "loawa" / "loawa_seed_canonical.ndjson"
    output_dir = Path(args.output_dir).resolve() if args.output_dir else data_dir / "processed" / "armory_normalized"
    parquet_dir = Path(args.parquet_dir).resolve() if args.parquet_dir else data_dir / "parquet" / "armory_normalized"
    statuses = {value.strip() for value in str(args.status).split(",") if value.strip()}

    canonical_rows = read_ndjson(canonical_path)
    selected_rows: list[dict[str, Any]] = []
    for row in canonical_rows:
        if (row.get("armoryStatus") or "") not in statuses:
            continue
        raw_path = row.get(args.source_field) or row.get("armoryRawPath") or row.get("apiRawPath")
        if not raw_path:
            continue
        selected_rows.append(row)
        if args.limit and len(selected_rows) >= args.limit:
            break

    if not selected_rows:
        raise RuntimeError("No canonical rows matched the requested filter.")

    character_rows: list[dict[str, Any]] = []
    accessory_rows: list[dict[str, Any]] = []
    accessory_effect_rows: list[dict[str, Any]] = []
    stone_rows: list[dict[str, Any]] = []
    bracelet_rows: list[dict[str, Any]] = []
    bracelet_effect_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for index, canonical_row in enumerate(selected_rows, start=1):
        raw_path = str(canonical_row.get(args.source_field) or canonical_row.get("armoryRawPath") or canonical_row.get("apiRawPath"))
        bundle_path = Path(raw_path)
        print(f"[ARMORY-NORMALIZE] {index}/{len(selected_rows)} {canonical_row.get('characterName')} -> {bundle_path.name}")
        try:
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            summary = build_character_summary(bundle, raw_saved_path=raw_path)
            class_preset = resolve_class_engraving_preset(summary, bundle)
            summary.class_engraving_preset = class_preset

            char_row = build_character_row(canonical_row, summary, class_preset, bundle, raw_path)
            character_rows.append(char_row)
            snapshot_id = char_row["snapshot_id"]

            acc_rows, acc_effect_rows, br_rows, br_effect_rows = build_accessory_rows(
                snapshot_id=snapshot_id,
                summary=summary,
                class_preset=class_preset,
                raw_path=raw_path,
            )
            accessory_rows.extend(acc_rows)
            accessory_effect_rows.extend(acc_effect_rows)
            bracelet_rows.extend(br_rows)
            bracelet_effect_rows.extend(br_effect_rows)

            stone_row = build_stone_row(
                snapshot_id=snapshot_id,
                summary=summary,
                class_preset=class_preset,
                raw_path=raw_path,
            )
            if stone_row:
                stone_rows.append(stone_row)
        except Exception as exc:  # pragma: no cover - data dependent
            errors.append(
                {
                    "character_name": canonical_row.get("characterName"),
                    "server_name": canonical_row.get("serverName"),
                    "raw_path": raw_path,
                    "error": str(exc),
                }
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    parquet_dir.mkdir(parents=True, exist_ok=True)

    dataset_map: dict[str, list[dict[str, Any]]] = {
        "character_snapshots": character_rows,
        "accessory_items": accessory_rows,
        "accessory_effects": accessory_effect_rows,
        "ability_stones": stone_rows,
        "bracelet_items": bracelet_rows,
        "bracelet_effects": bracelet_effect_rows,
        "errors": errors,
    }

    parquet_status: dict[str, str] = {}
    for name, rows in dataset_map.items():
        write_ndjson(output_dir / f"{name}.ndjson", rows)
        if not args.skip_parquet and name != "errors":
            parquet_status[name] = try_write_parquet(parquet_dir / f"{name}.parquet", rows)

    summary = {
        "normalizedAt": now_iso(),
        "canonicalPath": str(canonical_path),
        "outputDir": str(output_dir),
        "parquetDir": str(parquet_dir),
        "sourceField": args.source_field,
        "includedStatuses": sorted(statuses),
        "selectedCharacters": len(selected_rows),
        "counts": {
            "character_snapshots": len(character_rows),
            "accessory_items": len(accessory_rows),
            "accessory_effects": len(accessory_effect_rows),
            "ability_stones": len(stone_rows),
            "bracelet_items": len(bracelet_rows),
            "bracelet_effects": len(bracelet_effect_rows),
            "errors": len(errors),
        },
        "parquetStatus": parquet_status,
    }
    (output_dir / "normalization_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("[ARMORY-NORMALIZE] done")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
