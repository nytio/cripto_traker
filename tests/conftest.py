import os
import sys

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")

if WEB_DIR not in sys.path:
    sys.path.insert(0, WEB_DIR)


@pytest.fixture()
def app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret")
    monkeypatch.setenv("COINGECKO_BASE_URL", "https://api.coingecko.com/api/v3")
    monkeypatch.setenv("COINGECKO_VS_CURRENCY", "usd")
    monkeypatch.setenv("MAX_HISTORY_DAYS", "365")
    monkeypatch.setenv("COINGECKO_REQUEST_DELAY", "0")
    monkeypatch.setenv("COINGECKO_RETRY_COUNT", "0")
    monkeypatch.setenv("COINGECKO_RETRY_DELAY", "0")
    monkeypatch.setenv("PROPHET_FUTURE_DAYS", "0")
    monkeypatch.setenv("RNN_FUTURE_DAYS", "0")

    from app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    return app


@pytest.fixture()
def client(app):
    return app.test_client()
