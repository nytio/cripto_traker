from datetime import date, datetime, timezone
from decimal import Decimal

from app.db import get_session
from app.models import Cryptocurrency, Price
from app.services.price_updater import update_daily_prices


class FakeCoinGeckoClient:
    def __init__(self, prices):
        self._prices = prices

    def get_market_chart_range(self, coingecko_id, vs_currency, from_ts, to_ts):
        return {"prices": self._prices}


def _ts_ms(day: date, hour: int) -> int:
    return int(datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc).timestamp() * 1000)


def test_update_daily_prices_fills_missing_days(app):
    session = get_session()
    crypto = Cryptocurrency(name="Bitcoin", symbol="BTC", coingecko_id="bitcoin")
    session.add(crypto)
    session.commit()

    session.add(
        Price(crypto_id=crypto.id, date=date(2024, 1, 1), price=Decimal("100.0"))
    )
    session.commit()

    prices = [
        [_ts_ms(date(2024, 1, 2), 12), 110.0],
        [_ts_ms(date(2024, 1, 3), 12), 120.0],
    ]
    client = FakeCoinGeckoClient(prices)

    result = update_daily_prices(
        client, vs_currency="usd", as_of=date(2024, 1, 3), request_delay=0
    )

    assert result["updated"] == 1
    assert result["inserted"] == 2
    assert result["errors"] == []

    stored = session.query(Price).filter(Price.crypto_id == crypto.id).all()
    assert {row.date for row in stored} == {
        date(2024, 1, 1),
        date(2024, 1, 2),
        date(2024, 1, 3),
    }
