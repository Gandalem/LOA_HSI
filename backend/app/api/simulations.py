from __future__ import annotations

import numpy as np
from fastapi import APIRouter

from app.models.schemas import AbilityStoneSummary, CompareRequest, CompareResponse, ModuleCompareResult
from app.services.character_parser import build_character_summary
from app.services.class_preset import resolve_class_engraving_preset
from app.services.comparison_pipeline import (
    MODEL_VERSION,
    build_character_expected_values,
    build_price_fingerprint,
)
from app.services.dataset_writer import DatasetWriter
from app.services.lostark_client import LostArkClient
from app.services.simulation_engine import SimulationEngine
from app.services.simulation_store import SimulationStore, make_cache_key

router = APIRouter(prefix="/simulations", tags=["simulations"])


def _points_from_stone_type(value: str | None):
    if not value:
        return None
    try:
        left, right = str(value).split("/", 1)
        return int(left), int(right)
    except Exception:
        return None


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
        positive_2_points=int(p2),
        negative_name=override.negativeName or (old.negative_name if old else None) or "감소",
        negative_points=override.negativePoints,
        stone_type=f"{high}/{low}",
        quality=(old.quality if old else None),
        raw_tooltip_excerpt=(old.raw_tooltip_excerpt if old else None),
    )
    return character


@router.post("/compare-character", response_model=CompareResponse)
def compare_character(req: CompareRequest) -> CompareResponse:
    bundle, raw_path = LostArkClient().get_character_bundle(
        req.characterName,
        use_cache=req.useCachedCharacter,
    )
    character = build_character_summary(bundle, raw_saved_path=raw_path)
    character.class_engraving_preset = resolve_class_engraving_preset(character, bundle)
    character = apply_stone_override(character, req.stoneOverride)

    compare_context = build_character_expected_values(character, req.memoryHints)
    ability_stone_market = compare_context["abilityStoneMarket"]
    ability_stone_unit_price = float(compare_context["abilityStoneUnitPriceGold"])
    expected_values = compare_context["expectedValues"]

    engine = SimulationEngine(
        use_support_materials=False,
        ability_stone_price_gold=ability_stone_unit_price,
    )
    store = SimulationStore()

    selected_modules = [
        module
        for module in req.compareModules
        if module in {"equipment", "abilityStone", "accessory"}
    ]
    krw_per_gold = float(req.krwPer100Gold) / 100.0
    price_fingerprint = build_price_fingerprint(
        engine,
        ability_stone_unit_price,
        ability_stone_market,
    )
    cache_key = make_cache_key(
        character,
        selected_modules,
        req.simulationCount,
        req.seed,
        model_version=MODEL_VERSION,
        price_fingerprint=price_fingerprint,
    )
    cache_hit = store.exists(cache_key)

    assumptions = [
        "캐릭터 API는 현재 결과물만 보여주며 실제 사용 비용은 포함하지 않습니다.",
        "장비 재련은 로컬 T4 재련표와 저장된 재료 시세 기준으로 계산합니다.",
        "어빌리티 스톤은 같은 이름/등급/T4/긍정 각인 2개 일치 매물 기준으로 봅니다. 감소 각인은 비교하지 않습니다.",
        "장신구는 공식 옵션 확률표와 응답 Options 직접 검증 기준으로 계산합니다.",
        "팔찌 베이스 가격은 현재 팔찌의 고정 효과만 기준으로 4티어 고대 경매장 매물을 조회합니다.",
        "팔찌 랜덤 옵션은 고정 옵션과 분리해서 공식 확률표 기준으로 계산합니다.",
        "기억 기반 실제 비용 입력은 브라우저 localStorage 기준이며 서버 공용 데이터로 자동 저장하지 않습니다.",
        "실제 비용 미입력 모드에서는 운 수치보다 재현 비용 분포와 기억 기반 단서를 우선 표시합니다.",
        f"재료 가격 fingerprint: {engine.material_price_fingerprint[:12]}... / rows={len(engine.material_price_rows)}",
        f"어빌리티 스톤 단가: {ability_stone_unit_price:.0f}G ({ability_stone_market.get('matchingMode')})",
    ]
    assumptions.append(
        "기존 DuckDB 시뮬레이션 캐시를 사용했습니다."
        if cache_hit
        else "새 DuckDB 시뮬레이션 캐시를 생성했습니다."
    )

    if not cache_hit:
        module_values: dict[str, np.ndarray] = {}
        if "equipment" in selected_modules:
            module_values["equipment"] = engine.simulate_equipment_cost(
                character,
                req.simulationCount,
                req.seed,
            )
        if "abilityStone" in selected_modules:
            module_values["abilityStone"] = engine.simulate_stone_cost(
                character,
                req.simulationCount,
                req.seed,
            )
        if "accessory" in selected_modules:
            module_values["accessory"] = engine.simulate_accessory_cost(
                character,
                req.simulationCount,
                req.seed,
            )
        store.save(
            cache_key,
            character.character_name,
            selected_modules,
            req.simulationCount,
            req.seed,
            module_values,
            model_version=MODEL_VERSION,
        )

    modules: dict[str, ModuleCompareResult] = {}
    if "equipment" in selected_modules:
        modules["equipment"] = store.build_module_result(
            cache_key,
            "equipment",
            req.actualCostGold.equipment,
            krw_per_gold,
        )
    if "abilityStone" in selected_modules:
        modules["abilityStone"] = store.build_module_result(
            cache_key,
            "abilityStone",
            req.actualCostGold.abilityStone,
            krw_per_gold,
        )
    if "accessory" in selected_modules:
        modules["accessory"] = store.build_module_result(
            cache_key,
            "accessory",
            req.actualCostGold.accessory,
            krw_per_gold,
        )

    total_actual = (
        req.actualCostGold.equipment
        + req.actualCostGold.abilityStone
        + req.actualCostGold.accessory
    )
    total = store.build_module_result(cache_key, "total", total_actual, krw_per_gold)
    artifact_paths = store.artifact_paths(cache_key)
    artifact_paths["materialPriceFingerprint"] = engine.material_price_fingerprint
    artifact_paths["materialPriceRows"] = str(len(engine.material_price_rows))
    artifact_paths["modelVersion"] = MODEL_VERSION
    artifact_paths["actualCostMode"] = "not_provided" if total_actual <= 0 else "provided"
    artifact_paths["abilityStoneUnitPriceGold"] = str(ability_stone_unit_price)

    expected_values["actualCostMode"] = artifact_paths["actualCostMode"]
    expected_values["calculationBasis"] = {
        "official": [
            "장신구 효과 공식 확률표 매칭",
            "장신구 중복 제외 보정 기대 시도 수",
            "팔찌 T4 효과 개수 확률표",
            "팔찌 T4 고정/랜덤 옵션 분리 추정",
            "팔찌 T4 수동 입력 우선 적용",
            "스톤 활성 레벨-성공 횟수 변환",
        ],
        "estimate": [
            "장비 재련 재료 기반 재현 비용",
            "어빌리티 스톤 경매장 단가 기반 기대 스톤 개수",
            "장신구 유사 매물 조건 기반 시장가 추정",
            "팔찌 고정 효과 기반 경매장 베이스 가격 + 랜덤 옵션 기대 시도",
            "팔찌 옵션 개별 수치 구간은 카테고리 기준으로 표시",
        ],
        "memory": [
            "장기백 기록",
            "스톤 시도 개수",
            "장신구 직접 옵션 시도 수",
            "팔찌 랜덤 옵션 시도 수",
            "팔찌 고정 옵션 수",
            "팔찌 랜덤 슬롯 수",
            "브라우저 localStorage 불러오기",
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
