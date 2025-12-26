import pytest

from app.services.coincap import CoincapClient, CoincapError


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


def test_get_asset_history_success(monkeypatch):
    response = FakeResponse(200, json_data={"data": [{"priceUsd": "123", "time": 0}]})
    fake_requests = FakeRequests(response)
    monkeypatch.setattr("app.services.coincap.requests", fake_requests)

    client = CoincapClient("https://api.coincap.io/v2")
    data = client.get_asset_history("bitcoin", 0, 1)

    assert data["data"][0]["priceUsd"] == "123"


def test_get_asset_history_not_found(monkeypatch):
    response = FakeResponse(404, json_data={"error": "not found"}, ok=False)
    fake_requests = FakeRequests(response)
    monkeypatch.setattr("app.services.coincap.requests", fake_requests)

    client = CoincapClient("https://api.coincap.io/v2")
    with pytest.raises(CoincapError):
        client.get_asset_history("unknown", 0, 1)


def test_get_asset_history_server_error(monkeypatch):
    response = FakeResponse(500, json_data={"error": "server"}, ok=False)
    fake_requests = FakeRequests(response)
    monkeypatch.setattr("app.services.coincap.requests", fake_requests)

    client = CoincapClient("https://api.coincap.io/v2")
    with pytest.raises(CoincapError):
        client.get_asset_history("bitcoin", 0, 1)
