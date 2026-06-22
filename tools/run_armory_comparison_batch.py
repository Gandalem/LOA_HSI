from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def load_backend_components():
    try:
        from app.services.character_parser import build_character_summary  # type: ignore
        from app.services.class_preset import resolve_class_engraving_preset  # type: ignore
        from app.services.comparison_dataset_writer import ComparisonDatasetWriter  # type: ignore
        from app.services.comparison_pipeline import (  # type: ignore
            MODEL_VERSION,
            build_character_expected_values,
            build_price_fingerprint,
        )
        from app.services.simulation_engine import SimulationEngine  # type: ignore
        from app.services.simulation_store import SimulationStore, make_cache_key  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        missing = getattr(exc, "name", None) or str(exc)
        raise SystemExit(
            "Missing Python dependency for backend comparison batch: "
            f"{missing}. Install backend requirements first with "
            "`python -m pip install -r backend/requirements.txt`."
        ) from exc

    return {
        "build_character_summary": build_character_summary,
        "resolve_class_engraving_preset": resolve_class_engraving_preset,
        "ComparisonDatasetWriter": ComparisonDatasetWriter,
        "MODEL_VERSION": MODEL_VERSION,
        "build_character_expected_values": build_character_expected_values,
        "build_price_fingerprint": build_price_fingerprint,
        "SimulationEngine": SimulationEngine,
        "SimulationStore": SimulationStore,
        "make_cache_key": make_cache_key,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run append-only market/simulation comparison batches from armory_normalized parquet."
    )
    parser.add_argument(
        "--data-dir",
        default=str(ROOT / "data"),
        help="Data root. Default: ./data",
    )
    parser.add_argument(
        "--input-parquet",
        default=None,
        help="Input character_snapshots parquet. Default: <data-dir>/parquet/armory_normalized/character_snapshots.parquet",
    )
    parser.add_argument(
        "--summary-dir",
        default=None,
        help="Run summary JSON output directory. Default: <data-dir>/processed/armory_comparison",
    )
    parser.add_argument(
        "--source-raw-column",
        default="source_raw_path",
        help="Column in the normalized parquet that points to the raw armory bundle JSON.",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Row offset within the normalized character snapshot parquet.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max rows to process. 0 means all rows after offset.",
    )
    parser.add_argument(
        "--character-name",
        default="",
        help="Optional exact character name filter before offset/limit.",
    )
    parser.add_argument(
        "--simulation-count",
        type=int,
        default=10000,
        help="Monte Carlo sample count per character. Default: 10000",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Base RNG seed passed to the simulation engine.",
    )
    parser.add_argument(
        "--krw-per-100-gold",
        type=float,
        default=12.0,
        help="KRW per 100 gold for percentile summary materialization.",
    )
    parser.add_argument(
        "--modules",
        default="equipment,abilityStone,accessory",
        help="Comma-separated simulation modules to include. Default: equipment,abilityStone,accessory",
    )
    parser.add_argument(
        "--run-label",
        default="",
        help="Optional human-readable run label stored in the dataset.",
    )
    parser.add_argument(
        "--sleep-ms",
        type=int,
        default=0,
        help="Optional delay between characters. Use this if you want to throttle auction traffic.",
    )
    parser.add_argument(
        "--request-interval-ms",
        type=int,
        default=750,
        help="Minimum interval between Lost Ark API requests in milliseconds. Default: 750",
    )
    parser.add_argument(
        "--retry-429-count",
        type=int,
        default=4,
        help="Per-request retry count when the Lost Ark API returns 429. Default: 4",
    )
    parser.add_argument(
        "--retry-429-sleep-seconds",
        type=float,
        default=5.0,
        help="Sleep between 429 request retries in seconds. Default: 5",
    )
    parser.add_argument(
        "--character-retries",
        type=int,
        default=2,
        help="Whole-character retry count when a character fails with HTTP 429. Default: 2",
    )
    parser.add_argument(
        "--character-retry-sleep-seconds",
        type=float,
        default=20.0,
        help="Sleep before retrying a character after HTTP 429. Default: 20",
    )
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def nested_get(obj: Any, *keys: str) -> Any:
    current = obj
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def load_input_rows(path: Path) -> list[dict[str, Any]]:
    import pandas as pd  # type: ignore

    frame = pd.read_parquet(path)
    return frame.to_dict("records")


def select_rows(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    filtered = rows
    if args.character_name:
        filtered = [row for row in filtered if str(row.get("character_name") or "") == args.character_name]
    if args.offset > 0:
        filtered = filtered[args.offset:]
    if args.limit > 0:
        filtered = filtered[: args.limit]
    return filtered


def parse_modules(text: str) -> list[str]:
    valid = {"equipment", "abilityStone", "accessory"}
    modules = [value.strip() for value in str(text).split(",") if value.strip()]
    selected = [module for module in modules if module in valid]
    if not selected:
        raise SystemExit("At least one valid module is required: equipment, abilityStone, accessory")
    return selected


def build_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"armorycmp_{timestamp}_{uuid.uuid4().hex[:8]}"


def configure_backend_env(args: argparse.Namespace, data_dir: Path) -> None:
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ["LOSTARK_MIN_REQUEST_INTERVAL_MS"] = str(int(args.request_interval_ms))
    os.environ["LOSTARK_RETRY_429_COUNT"] = str(int(args.retry_429_count))
    os.environ["LOSTARK_RETRY_429_SLEEP_SECONDS"] = str(float(args.retry_429_sleep_seconds))


def is_http_429(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return True
    detail = str(getattr(exc, "detail", "") or exc)
    return "429" in detail


def build_character_row(
    *,
    run_id: str,
    run_label: str,
    row_index: int,
    input_row: dict[str, Any],
    summary: Any,
    bundle: dict[str, Any],
    raw_path: str,
    model_version: str,
    simulation_count: int,
    seed: int,
    simulation_cache_key: str,
    simulation_cache_hit: bool,
    material_price_fingerprint: str,
    ability_stone_unit_price_gold: float,
    expected_values: dict[str, Any],
    processed_at: str,
    elapsed_seconds: float,
) -> dict[str, Any]:
    class_preset = summary.class_engraving_preset or {}
    ability_stone_market = expected_values.get("abilityStoneMarket") or {}
    official_accessory = expected_values.get("officialAccessoryEffects") or {}
    official_bracelet = expected_values.get("officialBraceletT4") or {}
    market_cost = expected_values.get("marketCost") or {}
    market_summary = market_cost.get("summary") or {}
    accessory_market_total = nested_get(market_cost, "accessoryMarket", "total") or {}
    bracelet_market = market_cost.get("braceletMarket") or {}

    return {
        "run_id": run_id,
        "run_label": run_label,
        "row_index": row_index,
        "processed_at": processed_at,
        "elapsed_seconds": elapsed_seconds,
        "normalized_snapshot_id": input_row.get("snapshot_id"),
        "normalized_bundle_fetched_at": input_row.get("bundle_fetched_at"),
        "normalized_source_field": input_row.get("source_field"),
        "source_raw_path": raw_path,
        "bundle_fetched_at": bundle.get("fetchedAt"),
        "model_version": model_version,
        "simulation_count": simulation_count,
        "seed": seed,
        "simulation_cache_key": simulation_cache_key,
        "simulation_cache_hit": simulation_cache_hit,
        "material_price_fingerprint": material_price_fingerprint,
        "character_name": summary.character_name,
        "server_name": summary.server_name,
        "class_name": summary.class_name,
        "character_level": safe_int(summary.character_level),
        "item_avg_level": safe_float(summary.item_avg_level),
        "equipment_count": len(summary.equipment or []),
        "accessory_count": len(summary.accessories or []),
        "warning_count": len(summary.warnings or []),
        "warnings_json": json_dumps(summary.warnings or []),
        "class_preset_role": class_preset.get("role"),
        "class_preset_engraving": class_preset.get("engravingName") or class_preset.get("engraving_name"),
        "class_preset_confidence": safe_float(class_preset.get("confidence")),
        "class_preset_json": json_dumps(class_preset),
        "ability_stone_unit_price_gold": safe_float(ability_stone_unit_price_gold),
        "ability_stone_market_status": ability_stone_market.get("status"),
        "ability_stone_market_mode": ability_stone_market.get("matchingMode"),
        "stone_target": nested_get(expected_values, "abilityStone", "target"),
        "stone_success_probability_per_stone": safe_float(
            nested_get(expected_values, "abilityStone", "successProbabilityPerStone")
        ),
        "stone_expected_stones": safe_float(nested_get(expected_values, "abilityStone", "expectedStones")),
        "stone_expected_gold": safe_float(nested_get(expected_values, "abilityStone", "expectedGold")),
        "official_accessory_role": official_accessory.get("role"),
        "official_accessory_matched_effect_count": safe_int(official_accessory.get("matchedEffectCount")),
        "official_accessory_unmatched_effect_count": safe_int(official_accessory.get("unmatchedEffectCount")),
        "official_accessory_items_count": safe_int(len(official_accessory.get("items") or [])),
        "official_accessory_most_difficult_expected_attempts": safe_float(
            nested_get(official_accessory, "mostDifficultItem", "expectedAttempts")
        ),
        "official_bracelet_role": official_bracelet.get("role"),
        "official_bracelet_grade": official_bracelet.get("grade"),
        "official_bracelet_random_success_probability": safe_float(
            nested_get(official_bracelet, "randomOptionBasis", "weightedSuccessProbability")
        ),
        "official_bracelet_random_expected_attempts": safe_float(
            nested_get(official_bracelet, "randomOptionBasis", "expectedAttempts")
        ),
        "accessory_market_status": accessory_market_total.get("status"),
        "accessory_market_item_count": safe_int(accessory_market_total.get("itemCount")),
        "accessory_market_connected_item_count": safe_int(accessory_market_total.get("auctionConnectedItemCount")),
        "accessory_market_median_gold": safe_float(accessory_market_total.get("medianGold")),
        "bracelet_market_status": nested_get(bracelet_market, "baseBraceletMarket", "status"),
        "bracelet_market_base_price_gold": safe_float(bracelet_market.get("baseBraceletPriceGold")),
        "bracelet_market_expected_reproduction_gold": safe_float(bracelet_market.get("expectedReproductionCostGold")),
        "market_reproduction_gold": safe_float(market_summary.get("marketReproductionGold")),
        "ability_stone_market_json": json_dumps(ability_stone_market),
        "official_accessory_json": json_dumps(official_accessory),
        "official_bracelet_json": json_dumps(official_bracelet),
        "market_cost_json": json_dumps(market_cost),
    }


def build_module_rows(
    *,
    run_id: str,
    run_label: str,
    input_row: dict[str, Any],
    summary: Any,
    simulation_cache_key: str,
    simulation_cache_hit: bool,
    module_results: dict[str, Any],
    processed_at: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for module_name, result in module_results.items():
        summary_payload = result.summary.model_dump()
        user_payload = result.user.model_dump()
        rows.append(
            {
                "run_id": run_id,
                "run_label": run_label,
                "processed_at": processed_at,
                "normalized_snapshot_id": input_row.get("snapshot_id"),
                "simulation_cache_key": simulation_cache_key,
                "simulation_cache_hit": simulation_cache_hit,
                "character_name": summary.character_name,
                "server_name": summary.server_name,
                "class_name": summary.class_name,
                "module": module_name,
                "avg_gold": safe_float(summary_payload.get("avgGold")),
                "p50_gold": safe_float(summary_payload.get("p50Gold")),
                "p75_gold": safe_float(summary_payload.get("p75Gold")),
                "p90_gold": safe_float(summary_payload.get("p90Gold")),
                "p95_gold": safe_float(summary_payload.get("p95Gold")),
                "p99_gold": safe_float(summary_payload.get("p99Gold")),
                "min_gold": safe_float(summary_payload.get("minGold")),
                "max_gold": safe_float(summary_payload.get("maxGold")),
                "std_gold": safe_float(summary_payload.get("stdGold")),
                "avg_krw": safe_float(summary_payload.get("avgKrw")),
                "p90_krw": safe_float(summary_payload.get("p90Krw")),
                "p99_krw": safe_float(summary_payload.get("p99Krw")),
                "user_verdict": user_payload.get("verdict"),
                "summary_json": json_dumps(summary_payload),
                "user_json": json_dumps(user_payload),
            }
        )
    return rows


def build_failure_row(
    *,
    run_id: str,
    run_label: str,
    row_index: int,
    input_row: dict[str, Any],
    raw_path: str | None,
    error: Exception,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "run_label": run_label,
        "row_index": row_index,
        "processed_at": now_iso(),
        "normalized_snapshot_id": input_row.get("snapshot_id"),
        "character_name": input_row.get("character_name"),
        "server_name": input_row.get("server_name"),
        "source_raw_path": raw_path,
        "error_type": error.__class__.__name__,
        "error_message": str(error),
        "traceback": traceback.format_exc(),
    }


def write_summary(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    modules = parse_modules(args.modules)

    data_dir = Path(args.data_dir).resolve()
    configure_backend_env(args, data_dir)
    backend = load_backend_components()
    input_parquet = (
        Path(args.input_parquet).resolve()
        if args.input_parquet
        else data_dir / "parquet" / "armory_normalized" / "character_snapshots.parquet"
    )
    summary_dir = (
        Path(args.summary_dir).resolve()
        if args.summary_dir
        else data_dir / "processed" / "armory_comparison"
    )

    rows = load_input_rows(input_parquet)
    selected_rows = select_rows(rows, args)
    if not selected_rows:
        raise SystemExit("No normalized character rows matched the requested selection.")

    run_id = build_run_id()
    run_label = args.run_label or run_id
    started_at = now_iso()
    started_clock = time.perf_counter()

    build_character_summary = backend["build_character_summary"]
    resolve_class_engraving_preset = backend["resolve_class_engraving_preset"]
    ComparisonDatasetWriter = backend["ComparisonDatasetWriter"]
    MODEL_VERSION = backend["MODEL_VERSION"]
    build_character_expected_values = backend["build_character_expected_values"]
    build_price_fingerprint = backend["build_price_fingerprint"]
    SimulationEngine = backend["SimulationEngine"]
    SimulationStore = backend["SimulationStore"]
    make_cache_key = backend["make_cache_key"]

    store = SimulationStore()
    writer = ComparisonDatasetWriter()
    krw_per_gold = float(args.krw_per_100_gold) / 100.0

    character_rows: list[dict[str, Any]] = []
    module_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []

    for index, input_row in enumerate(selected_rows, start=1):
        raw_path = str(input_row.get(args.source_raw_column) or "")
        print(
            f"[ARMORY-COMPARE-BATCH] {index}/{len(selected_rows)} "
            f"{input_row.get('character_name')} -> {Path(raw_path).name}"
        )
        started_character = time.perf_counter()
        attempt = 0
        last_exc: Exception | None = None
        while attempt <= args.character_retries:
            try:
                if not raw_path:
                    raise FileNotFoundError(
                        f"Missing raw armory path in column `{args.source_raw_column}`."
                    )
                bundle = json.loads(Path(raw_path).read_text(encoding="utf-8"))
                summary = build_character_summary(bundle, raw_saved_path=raw_path)
                class_preset = resolve_class_engraving_preset(summary, bundle)
                summary.class_engraving_preset = class_preset

                compare_context = build_character_expected_values(summary, memory_hints={})
                ability_stone_unit_price_gold = float(compare_context["abilityStoneUnitPriceGold"])
                expected_values = compare_context["expectedValues"]

                engine = SimulationEngine(
                    use_support_materials=False,
                    ability_stone_price_gold=ability_stone_unit_price_gold,
                )
                price_fingerprint = build_price_fingerprint(
                    engine,
                    ability_stone_unit_price_gold,
                    compare_context["abilityStoneMarket"],
                )
                cache_key = make_cache_key(
                    summary,
                    modules,
                    args.simulation_count,
                    args.seed,
                    model_version=MODEL_VERSION,
                    price_fingerprint=price_fingerprint,
                )
                cache_hit = store.exists(cache_key)
                if not cache_hit:
                    distributions: dict[str, Any] = {}
                    if "equipment" in modules:
                        distributions["equipment"] = engine.simulate_equipment_cost(
                            summary,
                            args.simulation_count,
                            args.seed,
                        )
                    if "abilityStone" in modules:
                        distributions["abilityStone"] = engine.simulate_stone_cost(
                            summary,
                            args.simulation_count,
                            args.seed,
                        )
                    if "accessory" in modules:
                        distributions["accessory"] = engine.simulate_accessory_cost(
                            summary,
                            args.simulation_count,
                            args.seed,
                        )
                    store.save(
                        cache_key,
                        summary.character_name,
                        modules,
                        args.simulation_count,
                        args.seed,
                        distributions,
                        model_version=MODEL_VERSION,
                    )

                module_results: dict[str, Any] = {}
                for module_name in modules:
                    module_results[module_name] = store.build_module_result(
                        cache_key,
                        module_name,
                        0,
                        krw_per_gold,
                    )
                module_results["total"] = store.build_module_result(
                    cache_key,
                    "total",
                    0,
                    krw_per_gold,
                )

                processed_at = now_iso()
                character_rows.append(
                    build_character_row(
                        run_id=run_id,
                        run_label=run_label,
                        row_index=index,
                        input_row=input_row,
                        summary=summary,
                        bundle=bundle,
                        raw_path=raw_path,
                        model_version=MODEL_VERSION,
                        simulation_count=args.simulation_count,
                        seed=args.seed,
                        simulation_cache_key=cache_key,
                        simulation_cache_hit=cache_hit,
                        material_price_fingerprint=engine.material_price_fingerprint,
                        ability_stone_unit_price_gold=ability_stone_unit_price_gold,
                        expected_values=expected_values,
                        processed_at=processed_at,
                        elapsed_seconds=round(time.perf_counter() - started_character, 3),
                    )
                )
                module_rows.extend(
                    build_module_rows(
                        run_id=run_id,
                        run_label=run_label,
                        input_row=input_row,
                        summary=summary,
                        simulation_cache_key=cache_key,
                        simulation_cache_hit=cache_hit,
                        module_results=module_results,
                        processed_at=processed_at,
                    )
                )
                last_exc = None
                break
            except Exception as exc:  # pragma: no cover - data/API dependent
                last_exc = exc
                if is_http_429(exc) and attempt < args.character_retries:
                    attempt += 1
                    print(
                        f"[ARMORY-COMPARE-BATCH] 429 retry {attempt}/{args.character_retries} "
                        f"for {input_row.get('character_name')} after {args.character_retry_sleep_seconds}s"
                    )
                    time.sleep(float(args.character_retry_sleep_seconds))
                    continue
                break

        if last_exc is not None:
            failure_rows.append(
                build_failure_row(
                    run_id=run_id,
                    run_label=run_label,
                    row_index=index,
                    input_row=input_row,
                    raw_path=raw_path or None,
                    error=last_exc,
                )
            )

        if args.sleep_ms > 0 and index < len(selected_rows):
            time.sleep(args.sleep_ms / 1000.0)

    finished_at = now_iso()
    duration_seconds = round(time.perf_counter() - started_clock, 3)
    run_row = {
        "run_id": run_id,
        "run_label": run_label,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "input_parquet_path": str(input_parquet),
        "source_raw_column": args.source_raw_column,
        "offset": args.offset,
        "limit": args.limit if args.limit > 0 else None,
        "character_name_filter": args.character_name or None,
        "selected_character_count": len(selected_rows),
        "processed_character_count": len(character_rows),
        "failed_character_count": len(failure_rows),
        "simulation_count": args.simulation_count,
        "seed": args.seed,
        "krw_per_100_gold": args.krw_per_100_gold,
        "modules_json": json_dumps(modules),
        "model_version": MODEL_VERSION,
    }

    dataset_result = writer.write_run(
        run_row=run_row,
        character_rows=character_rows,
        module_rows=module_rows,
        failure_rows=failure_rows,
    )
    summary_payload = {
        "startedAt": started_at,
        "finishedAt": finished_at,
        "durationSeconds": duration_seconds,
        "runId": run_id,
        "runLabel": run_label,
        "inputParquet": str(input_parquet),
        "selectedCharacters": len(selected_rows),
        "processedCharacters": len(character_rows),
        "failedCharacters": len(failure_rows),
        "simulationCount": args.simulation_count,
        "seed": args.seed,
        "modules": modules,
        "datasetResult": dataset_result,
    }
    summary_path = summary_dir / f"{run_id}_summary.json"
    write_summary(summary_path, summary_payload)

    print("[ARMORY-COMPARE-BATCH] done")
    print(
        json.dumps(
            {
                **summary_payload,
                "summaryPath": str(summary_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
