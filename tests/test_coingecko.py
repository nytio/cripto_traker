import pytest

from app.services.coingecko import CoinGeckoClient, CoinGeckoError


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


def test_get_coin_basic_success(monkeypatch):
    response = FakeResponse(
        200, json_data={"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"}
    )
    fake_requests = FakeRequests(response)
    monkeypatch.setattr("app.services.coingecko.requests", fake_requests)

    client = CoinGeckoClient("https://api.coingecko.com/api/v3")
    data = client.get_coin_basic("bitcoin")

    assert data["id"] == "bitcoin"
    assert data["symbol"] == "btc"
    assert data["name"] == "Bitcoin"


def test_get_coin_basic_not_found(monkeypatch):
    response = FakeResponse(404, json_data={"error": "not found"}, ok=False)
    fake_requests = FakeRequests(response)
    monkeypatch.setattr("app.services.coingecko.requests", fake_requests)

    client = CoinGeckoClient("https://api.coingecko.com/api/v3")
    data = client.get_coin_basic("unknown")

    assert data is None


def test_get_coin_basic_server_error(monkeypatch):
    response = FakeResponse(500, json_data={"error": "server"}, ok=False)
    fake_requests = FakeRequests(response)
    monkeypatch.setattr("app.services.coingecko.requests", fake_requests)

    client = CoinGeckoClient("https://api.coingecko.com/api/v3")
    with pytest.raises(CoinGeckoError):
        client.get_coin_basic("bitcoin")
