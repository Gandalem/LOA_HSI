from __future__ import annotations

import math
from typing import Any

from app.models.schemas import CharacterSummary
from app.services.ability_stone_market import build_ability_stone_market_summary, stone_market_unit_price
from app.services.accessory_probability import build_official_accessory_effect_summary
from app.services.bracelet_market import build_bracelet_fixed_market_summary
from app.services.bracelet_probability import build_official_bracelet_t4_summary
from app.services.expectation_calculator import build_expected_value_summary
from app.services.market_cost_model import build_market_cost_summary
from app.services.simulation_engine import SimulationEngine

MODEL_VERSION = "v60.26-bracelet-marketcost-version"


def _attempts_for_at_least_once(probability: float | None, target: float) -> float | None:
    if not probability or probability <= 0 or probability >= 1:
        return None
    return math.log(1.0 - target) / math.log(1.0 - probability)


def _market_gold(value: float | None) -> float | None:
    if value is None:
        return None
    if value >= 10000:
        return float(round(value / 1000) * 1000)
    if value >= 1000:
        return float(round(value / 100) * 100)
    return float(round(value))


def sync_legacy_bracelet_summary(expected_values: dict[str, Any], official_bracelet: dict | None) -> None:
    """Keep old React fields aligned with the v60.1 official bracelet model."""
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
    legacy["currentValidEffects"] = [
        row.get("rawEffect")
        for row in official_bracelet.get("targetEffects") or []
        if row.get("rawEffect")
    ]
    legacy["currentValidLikeEffects"] = legacy["currentValidEffects"]
    legacy["currentSecondaryEffects"] = []
    legacy["currentConditionalEffects"] = []
    legacy["currentNonCoreEffects"] = [
        row.get("rawEffect")
        for row in official_bracelet.get("unmatchedEffects") or []
        if row.get("rawEffect")
    ]
    legacy["formula"] = random_basis.get("formula") or "v60.1 official bracelet random-option basis"
    legacy["rule"] = "Legacy braceletT4 fields are synchronized from officialBraceletT4.randomOptionBasis."


def apply_bracelet_market_override(
    expected_values: dict[str, Any],
    character: CharacterSummary,
    memory_hints: dict[str, Any] | None,
) -> None:
    market_cost = expected_values.get("marketCost")
    if not isinstance(market_cost, dict):
        return
    bracelet_market = build_bracelet_fixed_market_summary(
        character,
        expected_values.get("officialBraceletT4"),
        memory_hints,
    )
    market_cost["version"] = MODEL_VERSION
    market_cost["source"] = "lostark_auction_api_verified_response_options_and_bracelet_fixed_effects"
    market_cost["braceletMarket"] = bracelet_market
    summary = market_cost.setdefault("summary", {})
    summary["braceletActualGold"] = bracelet_market.get("estimatedActualCostGold")
    summary["braceletExpectedGold"] = bracelet_market.get("expectedReproductionCostGold")
    accessory_median = summary.get("accessoryMedianGold")
    bracelet_cost = (
        bracelet_market.get("estimatedActualCostGold")
        or bracelet_market.get("expectedReproductionCostGold")
        or 0
    )
    summary["marketReproductionGold"] = (
        _market_gold(float(accessory_median) + float(bracelet_cost or 0))
        if accessory_median is not None
        else None
    )
    limits = [
        row
        for row in market_cost.get("limits", [])
        if "팔찌 가격이 연동" not in str(row)
    ]
    limits.append(
        "팔찌 베이스 가격은 현재 팔찌의 고정 효과만 기준으로 4티어 고대 경매장 매물을 조회합니다. 금액 하한 필터는 적용하지 않습니다."
    )
    market_cost["limits"] = limits


def build_price_fingerprint(
    engine: SimulationEngine,
    ability_stone_unit_price_gold: float,
    ability_stone_market: dict[str, Any],
) -> str:
    return (
        f"{engine.material_price_fingerprint}:"
        f"stone:{ability_stone_unit_price_gold:.0f}:"
        f"{ability_stone_market.get('status')}:"
        "bracelet-fixed-v60.26"
    )


def build_character_expected_values(
    character: CharacterSummary,
    memory_hints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    default_engine = SimulationEngine(use_support_materials=False)
    default_stone_price = float(
        default_engine.defaults.get("ability_stone", {}).get("default_stone_price_gold", 5000)
    )
    ability_stone_market = build_ability_stone_market_summary(
        character,
        fallback_price_gold=default_stone_price,
    )
    ability_stone_unit_price_gold = stone_market_unit_price(
        ability_stone_market,
        fallback_price_gold=default_stone_price,
    )

    expected_values = build_expected_value_summary(
        character,
        stone_price_gold=float(ability_stone_unit_price_gold),
        class_preset=character.class_engraving_preset,
    )
    expected_values["abilityStoneMarket"] = ability_stone_market
    expected_values["officialAccessoryEffects"] = build_official_accessory_effect_summary(
        character,
        class_preset=character.class_engraving_preset,
    )
    expected_values["officialBraceletT4"] = build_official_bracelet_t4_summary(
        character,
        class_preset=character.class_engraving_preset,
        memory_hints=memory_hints,
    )
    sync_legacy_bracelet_summary(expected_values, expected_values.get("officialBraceletT4"))
    expected_values["marketCost"] = build_market_cost_summary(
        character,
        expected_values.get("officialAccessoryEffects"),
        expected_values.get("officialBraceletT4"),
        memory_hints,
    )
    apply_bracelet_market_override(expected_values, character, memory_hints)
    return {
        "defaultStonePriceGold": default_stone_price,
        "abilityStoneMarket": ability_stone_market,
        "abilityStoneUnitPriceGold": ability_stone_unit_price_gold,
        "expectedValues": expected_values,
    }
