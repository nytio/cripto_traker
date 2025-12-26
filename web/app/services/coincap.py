import time

import requests


class CoincapError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CoincapClient:
    def __init__(
        self,
        base_url: str,
        retry_count: int = 2,
        retry_delay: float = 1.0,
        api_key: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.retry_count = max(retry_count, 0)
        self.retry_delay = max(retry_delay, 0.0)
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "crypto-tracker/1.0",
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

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
                raise CoincapError("Network error calling Coincap") from exc

            if response.status_code == 404:
                raise CoincapError("Coincap resource not found", status_code=404)
            if response.status_code in {429} or response.status_code >= 500:
                if attempt < self.retry_count:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise CoincapError(
                    f"Coincap API error ({response.status_code})",
                    status_code=response.status_code,
                )
            if not response.ok:
                raise CoincapError(
                    f"Coincap API error ({response.status_code})",
                    status_code=response.status_code,
                )
            return response.json()

        raise CoincapError("Coincap API error") from last_exc

    def get_asset_history(
        self, asset_id: str, start_ms: int, end_ms: int, interval: str = "d1"
    ) -> dict:
        return self._get(
            f"assets/{asset_id}/history",
            params={"interval": interval, "start": start_ms, "end": end_ms},
        )
