from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.core.settings import get_settings
from app.models.schemas import AbilityStoneSummary, CharacterSummary, EquipmentItem, ModuleCompareResult
from app.services.percentile import compare_user_cost, summarize_distribution
from app.services.material_price_store import MaterialPriceStore
from app.services.expectation_calculator import stone_target_probability


def _config_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "config"
    if path.exists():
        return path
    return Path("/app/backend/config")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_defaults() -> dict[str, Any]:
    return _load_json(_config_dir() / "simulation_defaults.json")


def _rng(seed: int | None) -> np.random.Generator:
    return np.random.default_rng(seed)


T4_ARMOR_SUPPORT_TABLE: dict[float, dict[str, tuple[int, float]]] = {
    0.10: {"빙하": (20, 0.0050)},
    0.05: {"빙하": (20, 0.0025)},
    0.04: {"빙하": (20, 0.0020)},
    0.03: {"빙하": (20, 0.0015)},
    0.0225: {"빙하": (25, 0.0012)},
    0.015: {"빙하": (25, 0.0006)},
    0.01: {"빙하": (25, 0.0004)},
    0.005: {"빙하": (50, 0.0002)},
}

T4_WEAPON_SUPPORT_TABLE: dict[float, dict[str, tuple[int, float]]] = {
    0.10: {"용암": (20, 0.0050)},
    0.05: {"용암": (20, 0.0025)},
    0.04: {"용암": (20, 0.0020)},
    0.03: {"용암": (20, 0.0015)},
    0.0225: {"용암": (25, 0.0012)},
    0.015: {"용암": (25, 0.0006)},
    0.01: {"용암": (25, 0.0004)},
    0.005: {"용암": (50, 0.0002)},
}


def _support_table_for(kind: str) -> dict[float, dict[str, tuple[int, float]]]:
    return T4_WEAPON_SUPPORT_TABLE if kind == "weapon" else T4_ARMOR_SUPPORT_TABLE


def support_material_rule(kind: str, base_rate: float) -> dict[str, tuple[int, float]]:
    table = _support_table_for(kind)
    for rate, rule in table.items():
        if abs(float(base_rate) - float(rate)) < 1e-9:
            return rule
    return {}


def expected_attempts_until_success(rate: float, artisan_gain: float = 3.0) -> float:
    """Expected number of attempts until success or artisan pity.

    This is a compact local approximation of the refining optimizer logic: compare
    the expected total gold cost with and without support materials. It accounts for
    the fact that repeated failures eventually end through artisan energy.
    """
    p = max(0.000001, min(1.0, float(rate)))
    gain = max(0.000001, float(artisan_gain))
    pity_attempts = max(1, int(np.ceil(100.0 / gain)))
    # E[N] for a geometric process truncated by pity: sum P(N >= i).
    return float(sum((1.0 - p) ** i for i in range(pity_attempts)))


class SimulationEngine:
    def __init__(self, use_support_materials: bool = False) -> None:
        self.settings = get_settings()
        # v27: 보조재료 최적화/자동 적용 제거. 인자는 API 호환성만 유지합니다.
        self.use_support_materials = False
        self.defaults = _load_defaults()
        self.material_store = MaterialPriceStore()
        self.material_prices_gold = dict(self.defaults.get("equipment", {}).get("material_prices_gold", {}))
        # DB에 수집된 최신 재료 시세가 있으면 기본값 위에 덮어씁니다.
        self.material_prices_gold.update(self.material_store.latest_price_map())
        self.material_price_fingerprint = self.material_store.latest_fingerprint()
        self.material_price_rows = self.material_store.latest_rows()
        table_file = self.defaults.get("equipment", {}).get("honing_table_file")
        self.honing_tables: dict[str, Any] = {}
        if table_file:
            table_path = _config_dir() / table_file
            if table_path.exists():
                self.honing_tables = _load_json(table_path)

    def _gear_kind(self, item: EquipmentItem) -> str:
        return "weapon" if item.slot == "무기" else "armor"

    def _grade_key(self, item: EquipmentItem) -> str | None:
        # 장비 이름을 먼저 봅니다. 같은 아이템 레벨 1730 근처라도
        # 에기르 장비와 운명의 전율 장비는 서로 다른 재련표를 사용합니다.
        name = str(item.name or "")
        if "운명의 전율" in name:
            return "t4_1730"
        if "에기르" in name:
            return "t4_1590"

        # 이름 파싱이 실패하면 아이템 레벨로 보조 판단합니다.
        if item.item_level is not None and item.item_level >= 1730:
            return "t4_1730"
        if item.item_level is not None and item.item_level >= 1590:
            return "t4_1590"
        # If item level parsing fails but honing is in a typical T4 range, use t4_1590 as default.
        if item.honing_level is not None and 11 <= item.honing_level <= 25:
            return "t4_1590"
        return None

    def support_materials_for(self, gear_kind: str, base_rate: float) -> dict[str, tuple[int, float]]:
        return support_material_rule(gear_kind, base_rate)

    def _support_cost_and_bonus(self, gear_kind: str, base_rate: float) -> tuple[float, float, dict[str, float]]:
        rule = self.support_materials_for(gear_kind, base_rate)
        if not rule:
            return 0.0, 0.0, {}
        support_amounts = {key: float(qty) for key, (qty, _bonus) in rule.items()}
        bonus = sum(float(bonus) for _qty, bonus in rule.values())
        return self._attempt_cost_from_amounts(support_amounts), bonus, support_amounts

    def _expected_level_cost(self, attempt_cost: float, success_rate: float, artisan_gain: float | None = None) -> float:
        gain = float(artisan_gain if artisan_gain is not None else self.defaults["equipment"].get("artisan_gain_default", 3.0))
        return float(attempt_cost) * expected_attempts_until_success(float(success_rate), gain)

    def _optimized_support_decision(self, gear_kind: str, base_rate: float, base_attempt_cost: float, artisan_gain: float | None = None) -> dict[str, Any]:
        """Return support-material optimization data for one honing step.

        `use_support_materials` means the user wants the optimizer to be allowed to
        use support materials. It does not force wasteful support use; the optimizer
        applies support materials only when the expected total cost decreases.
        """
        support_cost, support_bonus, support_amounts = self._support_cost_and_bonus(gear_kind, base_rate)
        missing_support_prices = [key for key in support_amounts if key not in self.material_prices_gold or float(self.material_prices_gold.get(key) or 0) <= 0]
        supported_rate = min(1.0, float(base_rate) + float(support_bonus)) if support_amounts else float(base_rate)
        no_support_expected = self._expected_level_cost(base_attempt_cost, base_rate, artisan_gain)
        with_support_expected = self._expected_level_cost(base_attempt_cost + support_cost, supported_rate, artisan_gain) if support_amounts and not missing_support_prices else no_support_expected
        recommended = bool(support_amounts and not missing_support_prices and with_support_expected < no_support_expected)
        enabled = bool(self.use_support_materials and recommended)
        return {
            "available": bool(support_amounts),
            "enabled": enabled,
            "recommended": recommended,
            "supportCost": support_cost,
            "supportBonus": support_bonus,
            "supportAmounts": support_amounts,
            "missingSupportPrices": missing_support_prices,
            "baseRate": float(base_rate),
            "supportedRate": supported_rate,
            "finalRate": supported_rate if enabled else float(base_rate),
            "baseAttemptCost": float(base_attempt_cost),
            "finalAttemptCost": float(base_attempt_cost) + (support_cost if enabled else 0.0),
            "expectedNoSupportGold": no_support_expected,
            "expectedWithSupportGold": with_support_expected,
            "expectedFinalGold": with_support_expected if enabled else no_support_expected,
            "expectedSavingGold": max(0.0, no_support_expected - with_support_expected) if recommended else 0.0,
        }

    def _attempt_cost_from_amounts(self, amount: dict[str, float]) -> float:
        prices = self.material_prices_gold
        total = 0.0
        for name, qty in amount.items():
            if name == "골드":
                total += float(qty)
            else:
                total += float(qty) * float(prices.get(name, 0.0))
        return total

    def _table_rule(self, item: EquipmentItem, next_level: int) -> tuple[float, float, float] | None:
        kind = self._gear_kind(item)
        grade_key = self._grade_key(item)
        if not grade_key or not self.honing_tables:
            return None
        table = self.honing_tables.get("gear_types", {}).get(kind, {}).get(grade_key, {})
        row = table.get(str(next_level))
        if not row:
            return None
        base_rate = float(row["baseProb"])
        base_cost = self._attempt_cost_from_amounts(row.get("amount", {}))
        artisan_gain = float(self.defaults["equipment"].get("artisan_gain_default", 3.0))
        # 보조재료 최적화 제거: 재련 기대값은 기본 재료 + 골드 + 기본 성공확률 기준입니다.
        return base_rate, base_cost, artisan_gain

    def _fallback_rule(self, next_level: int) -> tuple[float, float, float]:
        rules = self.defaults["equipment"].get("fallback_attempt_rules") or self.defaults["equipment"].get("attempt_rules") or {}
        if not rules:
            return 0.05, 10000.0, 3.0
        rule = rules.get(str(next_level)) or rules.get(str(max(map(int, rules.keys()))))
        rate = float(rule["success_rate"])
        attempt_cost = float(rule.get("gold", 0.0)) + float(rule.get("material_gold", 0.0))
        artisan_gain = float(rule.get("artisan_gain", self.defaults["equipment"].get("artisan_gain_default", 3.0)))
        return rate, attempt_cost, artisan_gain

    def simulate_equipment_cost(self, character: CharacterSummary, n: int, seed: int | None) -> np.ndarray:
        rng = _rng(seed)
        eq_defaults = self.defaults["equipment"]
        costs = np.zeros(n, dtype=np.float64)

        gear_items = [x for x in character.equipment if x.honing_level is not None]
        if not gear_items:
            # If parsing failed, use a conservative synthetic target.
            synthetic = [18, 18, 18, 18, 18, 19]
            for target in synthetic:
                self._simulate_one_gear(rng, costs, target, int(eq_defaults.get("base_honing_level", 10)), None)
            return costs

        for item in gear_items:
            target = int(item.honing_level or 0)
            start = int(eq_defaults.get("base_honing_level", 10))
            # Icepeng T4 tables start from target 11. If target is lower, nothing to simulate.
            self._simulate_one_gear(rng, costs, target, start, item)
        return costs

    def _simulate_one_gear(self, rng: np.random.Generator, costs: np.ndarray, target: int, start: int, item: EquipmentItem | None) -> None:
        for next_level in range(start + 1, target + 1):
            if item is not None:
                rule = self._table_rule(item, next_level)
            else:
                rule = None
            if rule is None:
                rule = self._fallback_rule(next_level)
            rate, attempt_cost, artisan_gain = rule

            artisan = np.zeros(costs.shape[0], dtype=np.float64)
            done = np.zeros(costs.shape[0], dtype=bool)
            safety = 0
            while not bool(done.all()):
                active = ~done
                active_count = int(active.sum())
                costs[active] += attempt_cost
                success = rng.random(active_count) < rate

                idx = np.where(active)[0]
                success_idx = idx[success]
                fail_idx = idx[~success]
                done[success_idx] = True
                artisan[fail_idx] += artisan_gain
                pity_idx = fail_idx[artisan[fail_idx] >= 100.0]
                if pity_idx.size:
                    done[pity_idx] = True
                safety += 1
                if safety > 5000:
                    done[:] = True

    def _stone_target(self, stone: AbilityStoneSummary | None) -> tuple[int, int]:
        if not stone or stone.positive_1_points is None or stone.positive_2_points is None:
            # API 표시값 기준 기본 목표: 활성 레벨 2/2.
            return (2, 2)
        high, low = sorted([int(stone.positive_1_points), int(stone.positive_2_points)], reverse=True)
        return high, low

    def simulate_stone_cost(self, character: CharacterSummary, n: int, seed: int | None) -> np.ndarray:
        """어빌리티 스톤 비용 분포.

        v21 변경: 한 돌씩 직접 세공 반복을 하지 않고, 공식 자동 세공 구조를
        DP로 계산한 목표 성공 확률 p를 사용합니다.
        표시된 1~4 값은 성공 횟수가 아니라 활성 레벨이므로,
        stone_target_probability에서 활성 레벨을 성공 횟수 기준으로 변환한 뒤 계산합니다.
        목표 달성까지 필요한 스톤 개수는 기하분포 Geometric(p)를 따르므로 기대값은 1/p입니다.
        """
        rng = _rng(None if seed is None else seed + 11)
        defaults = self.defaults["ability_stone"]
        target_high, target_low = self._stone_target(character.ability_stone)
        stone_price = float(defaults.get("default_stone_price_gold", 5000))
        facet_cost = float(defaults.get("facet_cost_gold", 0))
        per_stone_cost = stone_price + facet_cost
        p = stone_target_probability(int(target_high), int(target_low), None)
        if p <= 0:
            return np.full(n, float(defaults.get("max_stones_per_user", 10000)) * per_stone_cost, dtype=np.float64)
        stones_needed = rng.geometric(p, size=n).astype(np.float64)
        return stones_needed * per_stone_cost

    def simulate_accessory_cost(self, character: CharacterSummary, n: int, seed: int | None) -> np.ndarray:
        rng = _rng(None if seed is None else seed + 23)
        defaults = self.defaults["accessory"]
        base_total = float(defaults.get("default_accessory_total_gold", 300000))
        sigma = float(defaults.get("market_variance_sigma", 0.12))
        # Current accessories are market-cost elements, not pure luck. Use lognormal spread to model market variance.
        if character.accessories:
            qualities = [x.quality for x in character.accessories if x.quality is not None]
            avg_quality = float(np.mean(qualities)) if qualities else 80.0
            quality_mult = 1.0 + max(0.0, avg_quality - 80.0) / 100.0
            base_total *= quality_mult
        return rng.lognormal(mean=np.log(max(1.0, base_total)), sigma=sigma, size=n)

    def build_module_result(self, module: str, distribution: np.ndarray, actual: float, krw_per_gold: float) -> ModuleCompareResult:
        return ModuleCompareResult(
            module=module,
            summary=summarize_distribution(distribution, krw_per_gold),
            user=compare_user_cost(distribution, actual, krw_per_gold),
        )

    def save_distribution(self, character_name: str, module_values: dict[str, np.ndarray]) -> dict[str, str]:
        paths: dict[str, str] = {}
        out_dir = self.settings.data_dir / "parquet" / character_name
        out_dir.mkdir(parents=True, exist_ok=True)
        for module, values in module_values.items():
            path = out_dir / f"{module}_distribution.parquet"
            pd.DataFrame({"total_gold_cost": values}).to_parquet(path, index=False)
            paths[module] = str(path)
        return paths
