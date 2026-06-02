from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.schemas import SimulationRequest
from app.services.price_store import price_map_for_simulation


@dataclass(frozen=True)
class HoningStage:
    name: str
    success_rate: float
    pity_attempts: int
    gold_fee: int
    materials: Dict[str, int]


# 학습용 단순화 규칙입니다. 실제 로스트아크 수치와 다를 수 있습니다.
# 실제 과제에서는 공식/인게임 확인값으로 교체하세요.
SAMPLE_PRICES = {
    "honor_shard": 1.0,
    "guardian_stone": 3.0,
    "destruction_stone": 5.0,
    "leapstone": 40.0,
    "fusion_material": 20.0,
}

HONING_STAGES: List[HoningStage] = [
    HoningStage("1600->1601", 0.10, 18, 900, {"honor_shard": 1200, "guardian_stone": 260, "destruction_stone": 90, "leapstone": 18, "fusion_material": 14}),
    HoningStage("1601->1602", 0.095, 19, 950, {"honor_shard": 1280, "guardian_stone": 275, "destruction_stone": 96, "leapstone": 19, "fusion_material": 14}),
    HoningStage("1602->1603", 0.09, 20, 1000, {"honor_shard": 1360, "guardian_stone": 290, "destruction_stone": 102, "leapstone": 20, "fusion_material": 15}),
    HoningStage("1603->1604", 0.085, 21, 1050, {"honor_shard": 1440, "guardian_stone": 305, "destruction_stone": 108, "leapstone": 21, "fusion_material": 15}),
    HoningStage("1604->1605", 0.08, 22, 1100, {"honor_shard": 1520, "guardian_stone": 320, "destruction_stone": 114, "leapstone": 22, "fusion_material": 16}),
    HoningStage("1605->1606", 0.075, 23, 1150, {"honor_shard": 1600, "guardian_stone": 335, "destruction_stone": 120, "leapstone": 23, "fusion_material": 16}),
    HoningStage("1606->1607", 0.07, 24, 1200, {"honor_shard": 1680, "guardian_stone": 350, "destruction_stone": 126, "leapstone": 24, "fusion_material": 17}),
    HoningStage("1607->1608", 0.065, 25, 1250, {"honor_shard": 1760, "guardian_stone": 365, "destruction_stone": 132, "leapstone": 25, "fusion_material": 17}),
    HoningStage("1608->1609", 0.06, 26, 1300, {"honor_shard": 1840, "guardian_stone": 380, "destruction_stone": 138, "leapstone": 26, "fusion_material": 18}),
    HoningStage("1609->1610", 0.055, 27, 1350, {"honor_shard": 1920, "guardian_stone": 395, "destruction_stone": 144, "leapstone": 27, "fusion_material": 18}),
    HoningStage("1610->1611", 0.052, 28, 1400, {"honor_shard": 2050, "guardian_stone": 420, "destruction_stone": 155, "leapstone": 29, "fusion_material": 19}),
    HoningStage("1611->1612", 0.049, 29, 1450, {"honor_shard": 2180, "guardian_stone": 445, "destruction_stone": 166, "leapstone": 31, "fusion_material": 20}),
    HoningStage("1612->1613", 0.046, 30, 1500, {"honor_shard": 2310, "guardian_stone": 470, "destruction_stone": 177, "leapstone": 33, "fusion_material": 21}),
    HoningStage("1613->1614", 0.043, 31, 1550, {"honor_shard": 2440, "guardian_stone": 495, "destruction_stone": 188, "leapstone": 35, "fusion_material": 22}),
    HoningStage("1614->1615", 0.04, 32, 1600, {"honor_shard": 2570, "guardian_stone": 520, "destruction_stone": 199, "leapstone": 37, "fusion_material": 23}),
    HoningStage("1615->1616", 0.038, 33, 1650, {"honor_shard": 2700, "guardian_stone": 545, "destruction_stone": 210, "leapstone": 39, "fusion_material": 24}),
    HoningStage("1616->1617", 0.036, 34, 1700, {"honor_shard": 2830, "guardian_stone": 570, "destruction_stone": 221, "leapstone": 41, "fusion_material": 25}),
    HoningStage("1617->1618", 0.034, 35, 1750, {"honor_shard": 2960, "guardian_stone": 595, "destruction_stone": 232, "leapstone": 43, "fusion_material": 26}),
    HoningStage("1618->1619", 0.032, 36, 1800, {"honor_shard": 3090, "guardian_stone": 620, "destruction_stone": 243, "leapstone": 45, "fusion_material": 27}),
    HoningStage("1619->1620", 0.03, 37, 1850, {"honor_shard": 3220, "guardian_stone": 645, "destruction_stone": 254, "leapstone": 47, "fusion_material": 28}),
]


def _stage_cost(stage: HoningStage, prices: Dict[str, float]) -> float:
    material_cost = sum(qty * prices[item] for item, qty in stage.materials.items())
    return material_cost + stage.gold_fee


def simulate_honing(rng: np.random.Generator, users: int, prices: Dict[str, float]) -> Tuple[np.ndarray, np.ndarray]:
    total_cost = np.zeros(users, dtype=np.float64)
    max_fail_streak = np.zeros(users, dtype=np.int32)

    for stage in HONING_STAGES:
        raw_attempts = rng.geometric(stage.success_rate, size=users)
        attempts = np.minimum(raw_attempts, stage.pity_attempts)
        fails = attempts - 1
        total_cost += attempts * _stage_cost(stage, prices)
        max_fail_streak = np.maximum(max_fail_streak, fails)

    return total_cost, max_fail_streak


def _cut_one_stone(rng: np.random.Generator) -> Tuple[int, int, int]:
    """간단한 어빌리티 스톤 세공 전략 모델.

    실제 최적 전략이 아니라 발표용/학습용 휴리스틱입니다.
    성공률이 높으면 부족한 긍정 라인을 누르고, 낮으면 감소 라인을 누릅니다.
    """
    rate = 0.75
    pos_a = pos_b = neg = 0
    taps_a = taps_b = taps_neg = 0

    while taps_a < 10 or taps_b < 10 or taps_neg < 10:
        if rate >= 0.55 and (taps_a < 10 or taps_b < 10):
            if taps_a < 10 and (pos_a <= pos_b or taps_b >= 10):
                target = "a"
                taps_a += 1
            else:
                target = "b"
                taps_b += 1
        elif taps_neg < 10:
            target = "neg"
            taps_neg += 1
        else:
            if taps_a < 10:
                target = "a"
                taps_a += 1
            else:
                target = "b"
                taps_b += 1

        success = rng.random() < rate
        if success:
            if target == "a":
                pos_a += 1
            elif target == "b":
                pos_b += 1
            else:
                neg += 1
            rate = max(0.25, rate - 0.10)
        else:
            rate = min(0.75, rate + 0.10)

    return pos_a, pos_b, neg


def simulate_stones(
    rng: np.random.Generator,
    users: int,
    target_a: int,
    target_b: int,
    max_negative: int,
    stone_price_gold: int,
    hard_cap_stones: int = 10000,
) -> Tuple[np.ndarray, np.ndarray]:
    costs = np.zeros(users, dtype=np.float64)
    attempts_used = np.zeros(users, dtype=np.int32)

    for user_idx in range(users):
        for attempt in range(1, hard_cap_stones + 1):
            a, b, neg = _cut_one_stone(rng)
            if a >= target_a and b >= target_b and neg <= max_negative:
                attempts_used[user_idx] = attempt
                costs[user_idx] = attempt * stone_price_gold
                break
        if attempts_used[user_idx] == 0:
            attempts_used[user_idx] = hard_cap_stones
            costs[user_idx] = hard_cap_stones * stone_price_gold

    return costs, attempts_used


def simulate_accessories(rng: np.random.Generator, users: int, base_gold: int) -> np.ndarray:
    """악세 세팅비를 로그정규분포로 근사합니다.

    같은 목표 세팅이라도 매물 부족/품질/특성에 따라 가격이 크게 튀는 구조를 표현합니다.
    """
    sigma = 0.45
    mean = np.log(max(base_gold, 1)) - 0.5 * sigma * sigma
    return rng.lognormal(mean=mean, sigma=sigma, size=users)


def _histogram(values: np.ndarray, bins: int = 12) -> List[Dict[str, int]]:
    counts, edges = np.histogram(values, bins=bins)
    result = []
    for idx, count in enumerate(counts):
        left = int(edges[idx] // 1000)
        right = int(edges[idx + 1] // 1000)
        result.append({"label": f"{left:,}k~{right:,}k", "count": int(count)})
    return result


def run_simulation(req: SimulationRequest) -> Dict[str, object]:
    rng = np.random.default_rng(req.seed)
    users = req.users

    prices = SAMPLE_PRICES.copy()
    latest_prices = price_map_for_simulation() if req.use_latest_api_prices else {}
    # API로 수집한 가격 중 재련 재료 키가 있으면 샘플 가격을 덮어씁니다.
    for key in SAMPLE_PRICES:
        if key in latest_prices and latest_prices[key] > 0:
            prices[key] = latest_prices[key]

    price_source = "latest_api_prices" if req.use_latest_api_prices and latest_prices else "sample_prices"

    honing_cost, max_fail_streak = simulate_honing(rng, users, prices)

    if req.include_stone:
        stone_cost, stone_attempts = simulate_stones(
            rng=rng,
            users=users,
            target_a=req.stone_target_a,
            target_b=req.stone_target_b,
            max_negative=req.stone_max_negative,
            stone_price_gold=int(req.stone_price_gold or latest_prices.get("ability_stone", 5000)),
        )
    else:
        stone_cost = np.zeros(users, dtype=np.float64)
        stone_attempts = np.zeros(users, dtype=np.int32)

    if req.include_accessory:
        accessory_cost = simulate_accessories(rng, users, int(req.accessory_base_gold or latest_prices.get("accessory_base", 250000)))
    else:
        accessory_cost = np.zeros(users, dtype=np.float64)

    total_gold = honing_cost + stone_cost + accessory_cost
    total_krw = total_gold * req.krw_per_gold

    avg_gold = float(np.mean(total_gold))
    p50_gold = float(np.percentile(total_gold, 50))
    p90_gold = float(np.percentile(total_gold, 90))
    p99_gold = float(np.percentile(total_gold, 99))

    user_percentile: Optional[float] = None
    user_message: Optional[str] = None
    if req.actual_user_gold is not None:
        less_or_equal = np.mean(total_gold <= req.actual_user_gold)
        user_percentile = float(less_or_equal * 100)
        unlucky_top = 100 - user_percentile
        user_message = f"입력한 비용은 시뮬레이션 기준 상위 약 {unlucky_top:.1f}% 불운 구간입니다."

    parquet_path: Optional[str] = None
    if req.save_parquet:
        out_dir = Path("/app/data/parquet")
        if not out_dir.exists():
            out_dir = Path("data/parquet")
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        parquet_path = str(out_dir / f"simulation_result_{ts}.parquet")
        df = pd.DataFrame(
            {
                "user_id": np.arange(1, users + 1),
                "honing_gold": honing_cost,
                "stone_gold": stone_cost,
                "accessory_gold": accessory_cost,
                "total_gold": total_gold,
                "total_krw": total_krw,
                "max_fail_streak": max_fail_streak,
                "stone_attempts": stone_attempts,
            }
        )
        df.to_parquet(parquet_path, index=False)

    return {
        "users": users,
        "avg_gold": avg_gold,
        "p50_gold": p50_gold,
        "p90_gold": p90_gold,
        "p99_gold": p99_gold,
        "avg_krw": float(np.mean(total_krw)),
        "p50_krw": float(np.percentile(total_krw, 50)),
        "p90_krw": float(np.percentile(total_krw, 90)),
        "p99_krw": float(np.percentile(total_krw, 99)),
        "bad_luck_tax_gold": p90_gold - avg_gold,
        "bad_luck_tax_krw": (p90_gold - avg_gold) * req.krw_per_gold,
        "honing_avg_gold": float(np.mean(honing_cost)),
        "stone_avg_gold": float(np.mean(stone_cost)),
        "accessory_avg_gold": float(np.mean(accessory_cost)),
        "max_fail_streak_avg": float(np.mean(max_fail_streak)),
        "stone_attempts_avg": float(np.mean(stone_attempts)),
        "histogram": _histogram(total_gold),
        "user_percentile": user_percentile,
        "user_message": user_message,
        "parquet_path": parquet_path,
        "price_source": price_source,
        "assumptions": [
            "재련 단계별 필요 재료량과 성공 확률은 Open API 가격 데이터가 아니라 config/코드에 정의한 규칙을 사용합니다. 실제 조사값으로 교체하세요.",
            "비공식 현금거래 시세는 사용하지 않고, 입력한 krw_per_gold를 공식 과금 기준 원화 환산값으로 해석합니다.",
            "어빌리티 스톤 세공은 단순 휴리스틱 전략으로 근사했습니다. 실제 최적 전략과 다를 수 있습니다.",
        ],
    }
