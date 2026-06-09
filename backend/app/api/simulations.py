from __future__ import annotations

import numpy as np
from fastapi import APIRouter

from app.models.schemas import AbilityStoneSummary, CompareRequest, CompareResponse, ModuleCompareResult
from app.services.character_parser import build_character_summary
from app.services.lostark_client import LostArkClient
from app.services.simulation_engine import SimulationEngine
from app.services.simulation_store import SimulationStore, make_cache_key
from app.services.expectation_calculator import build_expected_value_summary
from app.services.class_preset import resolve_class_engraving_preset

router = APIRouter(prefix="/simulations", tags=["simulations"])
MODEL_VERSION = "v48-mobile-report-and-version-sync"


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
        "어빌리티 스톤은 표시 활성 레벨을 성공 횟수로 변환한 뒤 목표 확률과 기대 시도 수를 계산합니다.",
        "장신구/팔찌는 현재 효과와 사용자가 직접 입력한 시도 수만 억까/상쇄 단서에 반영합니다.",
        "장신구 실제 거래가 기반 평가는 아직 별도 기능으로 분리 예정입니다.",
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

    expected_values = build_expected_value_summary(
        character,
        stone_price_gold=float(engine.defaults.get("ability_stone", {}).get("default_stone_price_gold", 5000)),
        class_preset=character.class_engraving_preset,
    )

    return CompareResponse(
        character=character,
        total=total,
        modules=modules,
        assumptions=assumptions,
        artifactPaths=artifact_paths,
        expectedValues=expected_values,
    )
