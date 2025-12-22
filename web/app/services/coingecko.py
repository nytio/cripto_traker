import requests


class CoinGeckoClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def ping(self) -> dict:
        return self._get("ping")

    def get_current_price(self, coingecko_id: str, vs_currency: str = "usd") -> dict:
        return self._get(
            "simple/price",
            params={"ids": coingecko_id, "vs_currencies": vs_currency},
        )

    def get_market_chart(self, coingecko_id: str, vs_currency: str, days: int) -> dict:
        return self._get(
            f"coins/{coingecko_id}/market_chart",
            params={"vs_currency": vs_currency, "days": days},
        )
