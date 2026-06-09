from __future__ import annotations

import numpy as np

from app.models.schemas import PercentileSummary, UserLuckResult


def summarize_distribution(values: np.ndarray, krw_per_gold: float) -> PercentileSummary:
    if values.size == 0:
        values = np.array([0.0])
    return PercentileSummary(
        avgGold=float(np.mean(values)),
        p50Gold=float(np.percentile(values, 50)),
        p75Gold=float(np.percentile(values, 75)),
        p90Gold=float(np.percentile(values, 90)),
        p95Gold=float(np.percentile(values, 95)),
        p99Gold=float(np.percentile(values, 99)),
        minGold=float(np.min(values)),
        maxGold=float(np.max(values)),
        stdGold=float(np.std(values)),
        avgKrw=float(np.mean(values) * krw_per_gold),
        p90Krw=float(np.percentile(values, 90) * krw_per_gold),
        p99Krw=float(np.percentile(values, 99) * krw_per_gold),
    )


def verdict_from_percentile(percentile: float) -> str:
    if percentile >= 99:
        return "상위 1% 극단적 불운"
    if percentile >= 95:
        return "상위 5% 불운"
    if percentile >= 90:
        return "상위 10% 불운"
    if percentile >= 75:
        return "평균보다 비용이 많이 든 편"
    if percentile >= 50:
        return "보통보다 약간 비용이 든 편"
    if percentile >= 25:
        return "평균보다 운 좋은 편"
    return "매우 운 좋은 편"


def compare_user_cost(values: np.ndarray, actual_gold: float, krw_per_gold: float) -> UserLuckResult:
    if values.size == 0:
        values = np.array([0.0])
    avg = float(np.mean(values))
    if actual_gold <= 0:
        # v49: 기본 모드는 실제 사용 골드를 입력받지 않습니다.
        # 0G를 실제 비용으로 해석하면 "매우 운 좋은 편"처럼 오해될 수 있으므로
        # 유저 비용 percentile은 미입력 상태로 명시합니다.
        return UserLuckResult(
            actualGold=float(actual_gold),
            actualKrw=float(actual_gold * krw_per_gold),
            costPercentile=0.0,
            badLuckTopPercent=0.0,
            verdict="실제 비용 미입력",
            extraGoldVsAvg=0.0,
            extraKrwVsAvg=0.0,
        )
    cost_percentile = float(np.mean(values <= actual_gold) * 100.0)
    bad_luck_top = float(max(0.0, 100.0 - cost_percentile))
    return UserLuckResult(
        actualGold=float(actual_gold),
        actualKrw=float(actual_gold * krw_per_gold),
        costPercentile=cost_percentile,
        badLuckTopPercent=bad_luck_top,
        verdict=verdict_from_percentile(cost_percentile),
        extraGoldVsAvg=float(actual_gold - avg),
        extraKrwVsAvg=float((actual_gold - avg) * krw_per_gold),
    )
