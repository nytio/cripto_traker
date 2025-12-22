import requests


class CoinGeckoError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CoinGeckoClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "crypto-tracker/1.0",
        }

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = requests.get(url, params=params, timeout=10, headers=self.headers)
        except requests.RequestException as exc:
            raise CoinGeckoError("Network error calling CoinGecko") from exc

        if response.status_code == 404:
            raise CoinGeckoError("CoinGecko resource not found", status_code=404)
        if not response.ok:
            raise CoinGeckoError(
                f"CoinGecko API error ({response.status_code})",
                status_code=response.status_code,
            )
        return response.json()

    def ping(self) -> dict:
        return self._get("ping")

    def get_coin_basic(self, coingecko_id: str) -> dict | None:
        try:
            data = self._get(
                f"coins/{coingecko_id}",
                params={
                    "localization": "false",
                    "tickers": "false",
                    "market_data": "false",
                    "community_data": "false",
                    "developer_data": "false",
                    "sparkline": "false",
                },
            )
        except CoinGeckoError as exc:
            if exc.status_code == 404:
                return None
            raise
        return {
            "id": data.get("id"),
            "symbol": data.get("symbol"),
            "name": data.get("name"),
        }

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

    def get_market_chart_range(
        self, coingecko_id: str, vs_currency: str, from_ts: int, to_ts: int
    ) -> dict:
        return self._get(
            f"coins/{coingecko_id}/market_chart/range",
            params={
                "vs_currency": vs_currency,
                "from": from_ts,
                "to": to_ts,
            },
        )
