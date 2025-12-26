import time

import requests


class CoinGeckoError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CoinGeckoClient:
    def __init__(
        self,
        base_url: str,
        retry_count: int = 2,
        retry_delay: float = 1.0,
        api_key: str | None = None,
        api_key_header: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.retry_count = max(retry_count, 0)
        self.retry_delay = max(retry_delay, 0.0)
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "crypto-tracker/1.0",
        }
        if api_key:
            header = api_key_header or (
                "x-cg-pro-api-key"
                if "pro-api.coingecko.com" in self.base_url
                else "x-cg-demo-api-key"
            )
            self.headers[header] = api_key

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        last_exc: Exception | None = None
        for attempt in range(self.retry_count + 1):
            try:
                response = requests.get(
                    url, params=params, timeout=10, headers=self.headers
                )
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.retry_count:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise CoinGeckoError("Network error calling CoinGecko") from exc

            if response.status_code == 404:
                raise CoinGeckoError("CoinGecko resource not found", status_code=404)
            if response.status_code in {429} or response.status_code >= 500:
                if attempt < self.retry_count:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise CoinGeckoError(
                    f"CoinGecko API error ({response.status_code})",
                    status_code=response.status_code,
                )
            if not response.ok:
                raise CoinGeckoError(
                    f"CoinGecko API error ({response.status_code})",
                    status_code=response.status_code,
                )
            return response.json()

        raise CoinGeckoError("CoinGecko API error") from last_exc

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
