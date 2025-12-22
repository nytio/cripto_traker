from __future__ import annotations

from typing import Any

from .coingecko import CoinGeckoClient


def update_daily_prices(client: CoinGeckoClient) -> dict[str, Any]:
    """
    Placeholder for daily price updates.
    Implement DB reads, API calls, and upserts in a later step.
    """
    return {"updated": 0, "errors": 0}
