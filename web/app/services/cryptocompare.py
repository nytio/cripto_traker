import time

import requests


class CryptoCompareError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CryptoCompareClient:
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
            header = api_key_header or "authorization"
            if header.lower() == "authorization":
                self.headers[header] = f"Apikey {api_key}"
            else:
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
                raise CryptoCompareError("Network error calling CryptoCompare") from exc

            if response.status_code == 404:
                raise CryptoCompareError(
                    "CryptoCompare resource not found", status_code=404
                )
            if response.status_code in {429} or response.status_code >= 500:
                if attempt < self.retry_count:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise CryptoCompareError(
                    f"CryptoCompare API error ({response.status_code})",
                    status_code=response.status_code,
                )
            if not response.ok:
                raise CryptoCompareError(
                    f"CryptoCompare API error ({response.status_code})",
                    status_code=response.status_code,
                )
            payload = response.json()
            if isinstance(payload, dict) and payload.get("Response") == "Error":
                message = payload.get("Message") or "CryptoCompare API error"
                raise CryptoCompareError(message, status_code=response.status_code)
            return payload

        raise CryptoCompareError("CryptoCompare API error") from last_exc

    def get_histoday(
        self, symbol: str, vs_currency: str, limit: int, to_ts: int
    ) -> dict:
        return self._get(
            "histoday",
            params={
                "fsym": symbol.upper(),
                "tsym": vs_currency.upper(),
                "limit": max(limit, 0),
                "toTs": to_ts,
            },
        )
