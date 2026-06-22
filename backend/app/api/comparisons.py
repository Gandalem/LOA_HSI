from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.cohort_comparison_service import CohortComparisonService

router = APIRouter(prefix="/comparisons", tags=["comparisons"])


class CohortComparisonRequest(BaseModel):
    className: str
    classPresetRole: str | None = None
    itemAvgLevel: float | None = None
    equipmentAvgGold: float | None = None
    marketReproductionGold: float | None = None
    stoneExpectedGold: float | None = None
    accessoryExpectedAttempts: float | None = None
    braceletExpectedAttempts: float | None = None
    totalSimulationAvgGold: float | None = None
    minSampleCount: int = Field(default=30, ge=1, le=5000)


@router.post("/cohort-compare")
def cohort_compare(req: CohortComparisonRequest):
    return CohortComparisonService().compare(
        class_name=req.className,
        class_preset_role=req.classPresetRole,
        item_avg_level=req.itemAvgLevel,
        current_metrics={
            "equipmentAvgGold": req.equipmentAvgGold,
            "marketReproductionGold": req.marketReproductionGold,
            "stoneExpectedGold": req.stoneExpectedGold,
            "accessoryExpectedAttempts": req.accessoryExpectedAttempts,
            "braceletExpectedAttempts": req.braceletExpectedAttempts,
            "totalSimulationAvgGold": req.totalSimulationAvgGold,
        },
        min_sample_count=req.minSampleCount,
    )


@router.get("/cohort-status")
def cohort_status():
    return CohortComparisonService().dataset_status()
