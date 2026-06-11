from __future__ import annotations

import math

import numpy as np
from fastapi import APIRouter

from app.models.schemas import AbilityStoneSummary, CompareRequest, CompareResponse, ModuleCompareResult
from app.services.character_parser import build_character_summary
from app.services.lostark_client import LostArkClient
from app.services.simulation_engine import SimulationEngine
from app.services.simulation_store import SimulationStore, make_cache_key
from app.services.expectation_calculator import build_expected_value_summary
from app.services.accessory_probability import build_official_accessory_effect_summary
from app.services.bracelet_probability import build_official_bracelet_t4_summary
from app.services.market_cost_model import build_market_cost_summary
from app.services.dataset_writer import DatasetWriter
from app.services.class_preset import resolve_class_engraving_preset

router = APIRouter(prefix="/simulations", tags=["simulations"])
MODEL_VERSION = "v60.1-market-cost-calibrated"


def _points_from_stone_type(value: str | None):
    if not value:
        return None
    try:
        left, right = str(value).split("/", 1)
        return int(left), int(right)
    except Exception:
        return None


def _attempts_for_at_least_once(probability: float | None, target: float) -> float | None:
    if not probability or probability <= 0 or probability >= 1:
        return None
    return math.log(1.0 - target) / math.log(1.0 - probability)


def sync_legacy_bracelet_summary(expected_values: dict, official_bracelet: dict | None) -> None:
    """Keep old React fields aligned with the v60.1 official bracelet model.

    ResultPanel.jsx still reads expectedValues.braceletT4 in several places. Until that
    component is fully migrated, copy the official v60.1 random-option expectation into
    the legacy keys so the visible score and detail text do not use the old 1+ category
    probability model.
    """
    if not official_bracelet:
        return
    random_basis = official_bracelet.get("randomOptionBasis") or {}
    probability = random_basis.get("weightedSuccessProbability")
    expected_attempts = random_basis.get("expectedAttempts")
    if probability is None or expected_attempts is None:
        return

    legacy = expected_values.setdefault("braceletT4", {})
    legacy["version"] = "v60.1-legacy-synced-from-officialBraceletT4"
    legacy["targetProbabilityOneOrMoreValidSpecial"] = probability
    legacy["expectedAttemptsForValidSpecial"] = expected_attempts
    legacy["attemptsForAtLeastOnce"] = {
        "50%": _attempts_for_at_least_once(probability, 0.50),
        "90%": _attempts_for_at_least_once(probability, 0.90),
        "99%": _attempts_for_at_least_once(probability, 0.99),
    }
    legacy["byAssignedCount"] = random_basis.get("successProbabilityByAssignedCount") or {}
    legacy["randomOptionBasis"] = random_basis
    legacy["currentValidEffects"] = [row.get("rawEffect") for row in official_bracelet.get("targetEffects") or [] if row.get("rawEffect")]
    legacy["currentValidLikeEffects"] = legacy["currentValidEffects"]
    legacy["currentSecondaryEffects"] = []
    legacy["currentConditionalEffects"] = []
    legacy["currentNonCoreEffects"] = [row.get("rawEffect") for row in official_bracelet.get("unmatchedEffects") or [] if row.get("rawEffect")]
    legacy["formula"] = random_basis.get("formula") or "v60.1 공식 팔찌 랜덤 옵션 기대값을 사용합니다."
    legacy["rule"] = "v60.1부터 기존 braceletT4 표시값도 officialBraceletT4.randomOptionBasis 기준으로 동기화합니다."


def apply_stone_override(character, override):
    if not override or not override.enabled:
        return character
    by_type = _points_from_stone_type(getattr(override, "stoneType", None))
    if by_type:
        p1, p2 = by_type
    else:
        p1 = override.positive1Points
        p2 = override.positive2Points
    if p1 is None or p2 is None:
        return character
    high, low = sorted([int(p1), int(p2)], reverse=True)
    old = character.ability_stone
    character.ability_stone = AbilityStoneSummary(
        name=(old.name if old else None) or "직접 입력 어빌리티 스톤",
        grade=(old.grade if old else None),
        positive_1_name=override.positive1Name or (old.positive_1_name if old else None) or "각인 1",
        positive_1_points=int(p1),
        positive_2_name=override.positive2Name or (old.positive_2_name if old else None) or "각인 2",
        negative_name=override.negativeName or (old.negative_name if old else None) or "감소",
        negative_points=override.negativePoints,
        stone_type=f"{high}/{low}",
        quality=(old.quality if old else None),
        raw_tooltip_excerpt=(old.raw_tooltip_excerpt if old else None),
    )
    return character


@router.post("/compare-character", response_model=CompareResponse)
def compare_character(req: CompareRequest) -> CompareResponse:
    bundle, raw_path = LostArkClient().get_character_bundle(req.characterName, use_cache=req.useCachedCharacter)
    character = build_character_summary(bundle, raw_saved_path=raw_path)
    character.class_engraving_preset = resolve_class_engraving_preset(character, bundle)
    character = apply_stone_override(character, req.stoneOverride)
    engine = SimulationEngine(use_support_materials=False)
    store = SimulationStore()

    selected_modules = [m for m in req.compareModules if m in {"equipment", "abilityStone", "accessory"}]
    krw_per_gold = float(req.krwPer100Gold) / 100.0
    cache_key = make_cache_key(
        character,
        selected_modules,
        req.simulationCount,
        req.seed,
        model_version=MODEL_VERSION,
        price_fingerprint=engine.material_price_fingerprint,
    )
    cache_hit = store.exists(cache_key)

    assumptions = [
        "캐릭터 API는 현재 결과물만 보여주며 실제 사용 비용은 알 수 없습니다.",
        "장비 재련은 로컬 T4 재련표와 DB 재료 시세를 기준으로 기본 재료/기본 성공확률만 계산합니다.",
        "어빌리티 스톤은 API로 가져온 현재 활성 레벨 결과를 목표로 보고, 사용자가 기억한 시도 개수와 비교합니다.",
        "장신구 효과는 공식 확률표와 매칭한 뒤 중복 제외 보정 기반 기대 시도 수를 계산합니다.",
        "v60.1 시장가 모델은 사용자가 확인한 매물 가격대에 맞춰 장신구 유사 매물 비용과 팔찌 베이스+돌 비용을 낮게 보정해 표시합니다.",
        "v60.1 시장가 모델은 실제 거래소 매물 조회 전 단계의 임시 추정값입니다.",
        "팔찌 T4는 구매 시 고정 옵션과 랜덤 옵션 슬롯이 섞여 있고 구매 후 계정 귀속되는 구조로 해석합니다.",
        "팔찌 고정/랜덤 슬롯 수는 기본 자동 추정하며, 수동 입력이 있으면 수동 입력을 우선합니다.",
        "기억 기반 보조 판정은 프론트에서 브라우저 localStorage에만 저장할 수 있으며 서버 DB에는 사용자별 기억 기록으로 저장하지 않습니다.",
        "팔찌 현재 효과 전체를 하나의 랜덤 목표로 계산하지 않고, 직접 돌린 랜덤 옵션 슬롯 기준 기대값만 표시합니다.",
        "v60.1부터 기존 프론트 braceletT4 표시값도 officialBraceletT4의 필요 카테고리 개수 기준 기대값과 동기화합니다.",
        "v51부터 리포트 생성 시 캐릭터/장비/장신구/팔찌/스톤/기억 입력을 로컬 Parquet 데이터셋으로 저장합니다.",
        "팔찌 옵션 개별 수치 구간별 표기확률은 아직 카테고리 기준 확률과 분리해 표시합니다.",
        "실제 사용 골드를 입력받지 않는 기본 모드에서는 유저 비용 percentile 판정보다 재현 비용 분포와 기억 기반 단서를 우선합니다.",
        f"재료 가격 fingerprint: {engine.material_price_fingerprint[:12]}... · DB 시세 {len(engine.material_price_rows)}개 반영",
    ]
    if cache_hit:
        assumptions.append("이번 결과는 기존 DuckDB 시뮬레이션 캐시를 사용했습니다.")
    else:
        assumptions.append("이번 결과는 새로 시뮬레이션한 뒤 DuckDB에 저장했습니다.")

    if not cache_hit:
        module_values: dict[str, np.ndarray] = {}
        if "equipment" in selected_modules:
            module_values["equipment"] = engine.simulate_equipment_cost(character, req.simulationCount, req.seed)
        if "abilityStone" in selected_modules:
            module_values["abilityStone"] = engine.simulate_stone_cost(character, req.simulationCount, req.seed)
        if "accessory" in selected_modules:
            module_values["accessory"] = engine.simulate_accessory_cost(character, req.simulationCount, req.seed)
        store.save(cache_key, character.character_name, selected_modules, req.simulationCount, req.seed, module_values, model_version=MODEL_VERSION)

    modules: dict[str, ModuleCompareResult] = {}
    if "equipment" in selected_modules:
        modules["equipment"] = store.build_module_result(cache_key, "equipment", req.actualCostGold.equipment, krw_per_gold)
    if "abilityStone" in selected_modules:
        modules["abilityStone"] = store.build_module_result(cache_key, "abilityStone", req.actualCostGold.abilityStone, krw_per_gold)
    if "accessory" in selected_modules:
        modules["accessory"] = store.build_module_result(cache_key, "accessory", req.actualCostGold.accessory, krw_per_gold)

    total_actual = req.actualCostGold.equipment + req.actualCostGold.abilityStone + req.actualCostGold.accessory
    total = store.build_module_result(cache_key, "total", total_actual, krw_per_gold)
    artifact_paths = store.artifact_paths(cache_key)
    artifact_paths["materialPriceFingerprint"] = engine.material_price_fingerprint
    artifact_paths["materialPriceRows"] = str(len(engine.material_price_rows))
    artifact_paths["modelVersion"] = MODEL_VERSION
    artifact_paths["actualCostMode"] = "not_provided" if total_actual <= 0 else "provided"

    expected_values = build_expected_value_summary(
        character,
        stone_price_gold=float(engine.defaults.get("ability_stone", {}).get("default_stone_price_gold", 5000)),
        class_preset=character.class_engraving_preset,
    )
    expected_values["officialAccessoryEffects"] = build_official_accessory_effect_summary(
        character,
        class_preset=character.class_engraving_preset,
    )
    expected_values["officialBraceletT4"] = build_official_bracelet_t4_summary(
        character,
        class_preset=character.class_engraving_preset,
        memory_hints=req.memoryHints,
    )
    sync_legacy_bracelet_summary(expected_values, expected_values.get("officialBraceletT4"))
    expected_values["marketCost"] = build_market_cost_summary(
        character,
        expected_values.get("officialAccessoryEffects"),
        expected_values.get("officialBraceletT4"),
        req.memoryHints,
    )
    expected_values["actualCostMode"] = artifact_paths["actualCostMode"]
    expected_values["calculationBasis"] = {
        "official": [
            "장신구 효과 공식 확률표 매칭",
            "장신구 중복 제외 보정 기대 시도 수",
            "팔찌 T4 효과 개수 확률",
            "팔찌 T4 고정 옵션/랜덤 옵션 슬롯 자동 추정",
            "팔찌 T4 수동 입력 우선 적용",
            "스톤 활성 레벨-성공 횟수 변환",
        ],
        "estimate": [
            "장비 재련표 기반 재현 비용",
            "장신구 유사 매물 조건 기반 시장가 추정",
            "팔찌 베이스 가격 + 팔찌 돌 가격 × 시도 수",
            "팔찌 옵션 개별 수치 구간은 카테고리 기준으로 표시",
        ],
        "memory": [
            "장기백 기록",
            "스톤 시도 개수",
            "장신구 직접 옵션 시도 수",
            "팔찌 랜덤 옵션 시도 수",
            "팔찌 고정 옵션 수",
            "팔찌 랜덤 슬롯 수",
            "브라우저 localStorage 저장/불러오기",
        ],
    }

    try:
        dataset_result = DatasetWriter().write_report_snapshot(
            character,
            expected_values,
            req.memoryHints,
            MODEL_VERSION,
        )
        artifact_paths["datasetSnapshotId"] = dataset_result["snapshotId"]
        artifact_paths["datasetDate"] = dataset_result["date"]
        artifact_paths["datasetTables"] = ",".join(dataset_result["writtenTables"].keys())
        expected_values["datasetSnapshot"] = dataset_result
    except Exception as exc:
        artifact_paths["datasetError"] = str(exc)
        expected_values["datasetSnapshot"] = {"error": str(exc)}

    return CompareResponse(
        character=character,
        total=total,
        modules=modules,
        assumptions=assumptions,
        artifactPaths=artifact_paths,
        expectedValues=expected_values,
    )
