import pytest

from app.services.cryptocompare import CryptoCompareClient, CryptoCompareError


class FakeResponse:
    def __init__(self, status_code, json_data=None, ok=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.ok = ok if ok is not None else 200 <= status_code < 300

    def json(self):
        return self._json_data


class FakeRequests:
    def __init__(self, response):
        self._response = response

    def get(self, *args, **kwargs):
        return self._response


def test_get_histoday_success(monkeypatch):
    response = FakeResponse(200, json_data={"Data": {"Data": [{"time": 1, "close": 1}]}})
    fake_requests = FakeRequests(response)
    monkeypatch.setattr("app.services.cryptocompare.requests", fake_requests)

    client = CryptoCompareClient("https://min-api.cryptocompare.com/data/v2")
    payload = client.get_histoday("btc", "usd", limit=1, to_ts=123)

    assert payload["Data"]["Data"][0]["close"] == 1


def test_get_histoday_error_payload(monkeypatch):
    response = FakeResponse(
        200, json_data={"Response": "Error", "Message": "bad request"}, ok=True
    )
    fake_requests = FakeRequests(response)
    monkeypatch.setattr("app.services.cryptocompare.requests", fake_requests)

    client = CryptoCompareClient("https://min-api.cryptocompare.com/data/v2")
    with pytest.raises(CryptoCompareError):
        client.get_histoday("btc", "usd", limit=1, to_ts=123)
