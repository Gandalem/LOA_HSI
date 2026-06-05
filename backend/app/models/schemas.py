from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class EquipmentItem(BaseModel):
    slot: str
    name: str | None = None
    grade: str | None = None
    item_level: float | None = None
    honing_level: int | None = None
    quality: int | None = None
    is_accessory: bool = False
    polish_level: int | None = None
    enlightenment_points: int | None = None
    raw_tooltip_excerpt: str | None = None
    bracelet_effects: list[str] = Field(default_factory=list)
    accessory_effects: list[str] = Field(default_factory=list)


class AbilityStoneSummary(BaseModel):
    name: str | None = None
    grade: str | None = None
    positive_1_name: str | None = None
    positive_1_points: int | None = None
    positive_2_name: str | None = None
    positive_2_points: int | None = None
    negative_name: str | None = None
    negative_points: int | None = None
    stone_type: str | None = None
    quality: int | None = None
    raw_tooltip_excerpt: str | None = None


class CharacterSummary(BaseModel):
    character_name: str
    server_name: str | None = None
    class_name: str | None = None
    item_avg_level: float | None = None
    character_level: int | None = None
    equipment: list[EquipmentItem] = Field(default_factory=list)
    accessories: list[EquipmentItem] = Field(default_factory=list)
    ability_stone: AbilityStoneSummary | None = None
    warnings: list[str] = Field(default_factory=list)
    raw_saved_path: str | None = None
    class_engraving_preset: dict[str, Any] | None = None


CompareModule = Literal["equipment", "abilityStone", "accessory", "total"]


class ActualCostGold(BaseModel):
    equipment: float = 0
    abilityStone: float = 0
    accessory: float = 0


class StoneOverride(BaseModel):
    enabled: bool = False
    # UI에서는 7/7, 9/7처럼 하나의 스톤 타입만 고르게 한다.
    # 기존 API 호환성을 위해 positive1/positive2 필드도 계속 받는다.
    stoneType: str | None = None
    positive1Name: str | None = None
    positive1Points: int | None = Field(default=None, ge=0, le=10)
    positive2Name: str | None = None
    positive2Points: int | None = Field(default=None, ge=0, le=10)
    negativeName: str | None = None
    negativePoints: int | None = Field(default=None, ge=0, le=10)


class CompareRequest(BaseModel):
    characterName: str
    compareModules: list[CompareModule] = Field(default_factory=lambda: ["equipment", "abilityStone", "accessory"])
    actualCostGold: ActualCostGold = Field(default_factory=ActualCostGold)
    simulationCount: int = Field(default=100_000, ge=100, le=500_000)
    krwPer100Gold: float = Field(default=12.0, ge=0)
    seed: int | None = 42
    useCachedCharacter: bool = True
    useSupportMaterials: bool = False
    stoneOverride: StoneOverride = Field(default_factory=StoneOverride)


class PercentileSummary(BaseModel):
    avgGold: float
    p50Gold: float
    p75Gold: float
    p90Gold: float
    p95Gold: float
    p99Gold: float
    minGold: float
    maxGold: float
    stdGold: float
    avgKrw: float
    p90Krw: float
    p99Krw: float


class UserLuckResult(BaseModel):
    actualGold: float
    actualKrw: float
    costPercentile: float
    badLuckTopPercent: float
    verdict: str
    extraGoldVsAvg: float
    extraKrwVsAvg: float


class ModuleCompareResult(BaseModel):
    module: str
    summary: PercentileSummary
    user: UserLuckResult


class CompareResponse(BaseModel):
    character: CharacterSummary
    total: ModuleCompareResult
    modules: dict[str, ModuleCompareResult]
    assumptions: list[str]
    artifactPaths: dict[str, str] = Field(default_factory=dict)
    expectedValues: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    ok: bool
    service: str


class RawLostArkResponse(BaseModel):
    endpoint: str
    data: Any
