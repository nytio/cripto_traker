from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select

from ..db import get_session
from ..models import Cryptocurrency, Price
from .coingecko import CoinGeckoClient, CoinGeckoError


def load_historical_prices(
    client: CoinGeckoClient,
    crypto: Cryptocurrency,
    vs_currency: str,
    days: int,
) -> int:
    session = get_session()
    payload = client.get_market_chart(crypto.coingecko_id, vs_currency, days)
    prices = payload.get("prices", [])
    if not prices:
        return 0

    by_date: dict[date, Decimal] = {}
    for timestamp_ms, price in prices:
        dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).date()
        by_date[dt] = Decimal(str(price))

    records = [
        {"crypto_id": crypto.id, "date": day, "price": price}
        for day, price in by_date.items()
    ]
    stmt = insert(Price).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Price.crypto_id, Price.date],
        set_={"price": stmt.excluded.price},
    )
    try:
        session.execute(stmt)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return len(records)


def update_daily_prices(
    client: CoinGeckoClient, vs_currency: str, as_of: date | None = None
) -> dict[str, Any]:
    session = get_session()
    as_of = as_of or date.today()

    cryptos = session.execute(select(Cryptocurrency)).scalars().all()
    if not cryptos:
        return {"updated": 0, "errors": []}
    updated = 0
    errors: list[dict[str, str]] = []

    for crypto in cryptos:
        try:
            payload = client.get_current_price(crypto.coingecko_id, vs_currency=vs_currency)
            price_value = payload.get(crypto.coingecko_id, {}).get(vs_currency)
            if price_value is None:
                raise CoinGeckoError("Price not found in response")

            price_decimal = Decimal(str(price_value))
            stmt = insert(Price).values(
                crypto_id=crypto.id,
                date=as_of,
                price=price_decimal,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[Price.crypto_id, Price.date],
                set_={"price": price_decimal},
            )
            session.execute(stmt)
            session.commit()
            updated += 1
        except Exception as exc:
            session.rollback()
            errors.append({"crypto_id": str(crypto.id), "error": str(exc)})

    return {"updated": updated, "errors": errors}
