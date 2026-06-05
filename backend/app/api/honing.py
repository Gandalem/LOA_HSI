from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.simulation_engine import SimulationEngine

router = APIRouter(prefix="/honing", tags=["honing"])


def _display_material_name(key: str) -> str:
    names = {
        "운명의수호석": "운명의 수호석",
        "운명의파괴석": "운명의 파괴석",
        "운명의수호석결정": "운명의 수호석 결정",
        "운명의파괴석결정": "운명의 파괴석 결정",
        "운돌": "운명의 돌파석",
        "위운돌": "위대한 운명의 돌파석",
        "아비도스": "아비도스 융화 재료",
        "상급아비도스": "상급 아비도스 융화 재료",
        "운명파편": "운명의 파편",
        "골드": "골드",
        "빙하": "빙하의 숨결",
        "용암": "용암의 숨결",
    }
    return names.get(key, key)


def _format_materials(amount: dict[str, float]) -> list[dict[str, float | str]]:
    rows = []
    for key, qty in amount.items():
        rows.append({"key": key, "name": _display_material_name(key), "quantity": qty})
    return rows


@router.get("/table")
def honing_table() -> dict:
    """Return the local honing table used by the simulator.

    v27 기준: 보조재료 최적화/자동 적용은 제거했습니다. 표와 시뮬레이션은
    기본 성공확률과 기본 재료량 기준 1회 비용을 보여줍니다.
    """
    engine = SimulationEngine(use_support_materials=False)
    result_rows = []
    gear_types = engine.honing_tables.get("gear_types", {}) if engine.honing_tables else {}
    for gear_kind, grades in gear_types.items():
        gear_label = "무기" if gear_kind == "weapon" else "방어구"
        for grade_key, levels in grades.items():
            grade_label = {
                "t4_1590": "에기르 장비 · T4 1590 계열",
                "t4_1730": "운명의 전율 장비 · T4 1730 계열",
            }.get(grade_key, grade_key)
            for level_key in sorted(levels.keys(), key=lambda x: int(x)):
                row = levels[level_key]
                amount = row.get("amount", {}) or {}
                base_prob = float(row.get("baseProb", 0))
                base_attempt_cost = engine._attempt_cost_from_amounts(amount)
                result_rows.append({
                    "gearKind": gear_kind,
                    "gearLabel": gear_label,
                    "gradeKey": grade_key,
                    "gradeLabel": grade_label,
                    "targetLevel": int(level_key),
                    "baseSuccessRate": base_prob,
                    "baseSuccessRatePercent": base_prob * 100.0,
                    "successRate": base_prob,
                    "successRatePercent": base_prob * 100.0,
                    "materials": _format_materials(amount),
                    "amount": amount,
                    "baseAttemptCostGold": base_attempt_cost,
                    "attemptCostGold": base_attempt_cost,
                    "supportMaterialEnabled": False,
                    "supportMaterialNote": "보조재료 미적용",
                })
    return {
        "source": engine.honing_tables.get("source") if engine.honing_tables else None,
        "startingHoningLevel": engine.honing_tables.get("starting_honing_level") if engine.honing_tables else None,
        "materialPriceFingerprint": engine.material_price_fingerprint,
        "materialPriceRows": engine.material_price_rows,
        "supportMaterialPolicy": "미사용",
        "supportMaterialNote": "v27에서는 보조재료 최적화/자동 적용을 제거했습니다. 기본 재료비 기준으로 계산합니다.",
        "rows": result_rows,
    }
