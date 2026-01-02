from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.db import get_session
from app.models import Cryptocurrency, Price
from app.services.price_updater import fill_missing_prices


class FakeCoincapClient:
    def __init__(self, data):
        self._data = data

    def get_asset_history(self, asset_id, start_ms, end_ms, interval="d1"):
        return {"data": self._data}


def _ts_ms(day: date, hour: int) -> int:
    return int(
        datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc).timestamp()
        * 1000
    )


def test_fill_missing_prices_between_first_and_last(app):
    session = get_session()
    crypto = Cryptocurrency(name="Bitcoin", symbol="BTC", coingecko_id="bitcoin")
    session.add(crypto)
    session.commit()

    today = date.today()
    start = today - timedelta(days=4)
    end = today - timedelta(days=1)
    session.add(Price(crypto_id=crypto.id, date=start, price=Decimal("100.0")))
    session.add(Price(crypto_id=crypto.id, date=end, price=Decimal("130.0")))
    session.commit()

    missing_day_1 = today - timedelta(days=3)
    missing_day_2 = today - timedelta(days=2)
    data = [
        {"time": _ts_ms(missing_day_1, 12), "priceUsd": "110.0"},
        {"time": _ts_ms(missing_day_2, 12), "priceUsd": "120.0"},
    ]
    client = FakeCoincapClient(data)

    result = fill_missing_prices(
        crypto.id,
        vs_currency="usd",
        request_delay=0,
        coincap_client=client,
    )

    assert result["inserted"] == 2
    assert result["requested"] == 1
    assert result["has_history"] is True

    stored = session.query(Price).filter(Price.crypto_id == crypto.id).all()
    assert {row.date for row in stored} == {
        start,
        missing_day_1,
        missing_day_2,
        end,
    }
