from __future__ import annotations

from typing import Any

from app.models.schemas import CharacterSummary


def build_market_cost_summary(character: CharacterSummary, official_accessory: dict[str, Any] | None, official_bracelet: dict[str, Any] | None, memory_hints: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "version": "v60-market-cost-model",
        "source": "heuristic_until_trade_or_auction_api",
        "tradeApiConnected": False,
        "summary": {},
        "accessoryMarket": {"items": [], "total": {"itemCount": 0}},
        "braceletMarket": {"available": False},
        "limits": ["v60 first pass placeholder"]
    }
