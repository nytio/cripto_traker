from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import time as time_module
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import func, select

from ..db import get_session
from ..models import Cryptocurrency, Price

MAX_HISTORY_DAYS_DEFAULT = 3650
MAX_BACKFILL_CHUNK_DAYS = 365
from .coingecko import CoinGeckoClient, CoinGeckoError


def load_historical_prices(
    client: CoinGeckoClient,
    crypto: Cryptocurrency,
    vs_currency: str,
    days: int,
    request_delay: float = 1.1,
    max_history_days: int | None = None,
    max_request_days: int | None = None,
) -> int:
    if days <= 0:
        return 0
    result = backfill_historical_prices(
        crypto.id,
        client,
        vs_currency=vs_currency,
        days=days,
        request_delay=request_delay,
        max_history_days=max_history_days,
        max_request_days=max_request_days,
    )
    return result["inserted"]


def _upsert_price(
    session, crypto_id: int, as_of: date, price_decimal: Decimal
) -> None:
    stmt = insert(Price).values(
        crypto_id=crypto_id,
        date=as_of,
        price=price_decimal,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Price.crypto_id, Price.date],
        set_={"price": price_decimal},
    )
    session.execute(stmt)


def _price_exists(session, crypto_id: int, as_of: date) -> bool:
    return (
        session.execute(
            select(Price.id)
            .where(Price.crypto_id == crypto_id)
            .where(Price.date == as_of)
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )


def update_crypto_price(
    session, client: CoinGeckoClient, crypto: Cryptocurrency, vs_currency: str, as_of: date
) -> bool:
    if _price_exists(session, crypto.id, as_of):
        return False
    price_decimal = _fetch_historical_price(
        client, crypto.coingecko_id, vs_currency, as_of
    )
    _upsert_price(session, crypto.id, as_of, price_decimal)
    session.commit()
    return True


def update_single_price(
    crypto_id: int, client: CoinGeckoClient, vs_currency: str, as_of: date | None = None
) -> bool:
    session = get_session()
    today = date.today()
    as_of = as_of or today
    if as_of >= today:
        as_of = today - timedelta(days=1)
    crypto = session.execute(
        select(Cryptocurrency).where(Cryptocurrency.id == crypto_id)
    ).scalar_one_or_none()
    if not crypto:
        raise ValueError("Crypto not found")
    try:
        return update_crypto_price(session, client, crypto, vs_currency, as_of)
    except Exception:
        session.rollback()
        raise


def _to_timestamp(day: date, end_of_day: bool) -> int:
    if end_of_day:
        dt = datetime.combine(day, time(23, 59, 59), tzinfo=timezone.utc)
    else:
        dt = datetime.combine(day, time(0, 0, 0), tzinfo=timezone.utc)
    return int(dt.timestamp())


def _fetch_historical_price(
    client: CoinGeckoClient, coingecko_id: str, vs_currency: str, as_of: date
) -> Decimal:
    from_ts = _to_timestamp(as_of, end_of_day=False)
    to_ts = _to_timestamp(as_of, end_of_day=True)
    payload = client.get_market_chart_range(coingecko_id, vs_currency, from_ts, to_ts)
    prices = payload.get("prices", [])
    if not prices:
        raise CoinGeckoError("Historical price not found in response")
    timestamp_ms, price_value = max(prices, key=lambda item: item[0])
    if price_value is None:
        raise CoinGeckoError("Historical price not found in response")
    return Decimal(str(price_value))


def _compute_missing_ranges(
    start_date: date, end_date: date, existing_dates: set[date]
) -> list[tuple[date, date]]:
    missing_ranges: list[tuple[date, date]] = []
    current = start_date
    while current <= end_date:
        if current not in existing_dates:
            range_start = current
            while current <= end_date and current not in existing_dates:
                current += timedelta(days=1)
            range_end = current - timedelta(days=1)
            missing_ranges.append((range_start, range_end))
        else:
            current += timedelta(days=1)
    return missing_ranges


def _split_date_range(
    start_date: date, end_date: date, chunk_days: int
) -> list[tuple[date, date]]:
    if chunk_days <= 0:
        return [(start_date, end_date)]
    ranges: list[tuple[date, date]] = []
    current = start_date
    delta = timedelta(days=chunk_days - 1)
    while current <= end_date:
        chunk_end = min(current + delta, end_date)
        ranges.append((current, chunk_end))
        current = chunk_end + timedelta(days=1)
    return ranges


def backfill_historical_prices(
    crypto_id: int,
    client: CoinGeckoClient,
    vs_currency: str,
    days: int,
    request_delay: float = 1.1,
    max_history_days: int | None = None,
    max_request_days: int | None = None,
) -> dict[str, Any]:
    session = get_session()
    end_date = date.today() - timedelta(days=1)
    if days <= 0:
        return {"inserted": 0, "requested": 0, "ranges": []}
    max_days = (
        max_history_days
        if max_history_days is not None
        else MAX_HISTORY_DAYS_DEFAULT
    )
    max_chunk_days = (
        max_request_days
        if max_request_days is not None
        else MAX_BACKFILL_CHUNK_DAYS
    )
    if max_days <= 0:
        return {"inserted": 0, "requested": 0, "ranges": []}
    if days > max_days:
        days = max_days
    min_allowed_date = end_date - timedelta(days=max_days - 1)

    crypto = session.execute(
        select(Cryptocurrency).where(Cryptocurrency.id == crypto_id)
    ).scalar_one_or_none()
    if not crypto:
        raise ValueError("Crypto not found")

    if end_date < min_allowed_date:
        return {"inserted": 0, "requested": 0, "ranges": []}

    def build_window(target_end: date) -> tuple[date, date]:
        start = target_end - timedelta(days=days - 1)
        if start < min_allowed_date:
            start = min_allowed_date
        return start, target_end

    def fetch_existing_dates(start: date, end: date) -> set[date]:
        rows = session.execute(
            select(Price.date)
            .where(Price.crypto_id == crypto_id)
            .where(Price.date >= start)
            .where(Price.date <= end)
        ).all()
        return {row[0] for row in rows}

    start_date, end_date = build_window(end_date)
    existing_dates = fetch_existing_dates(start_date, end_date)
    missing_ranges = _compute_missing_ranges(start_date, end_date, existing_dates)

    if not missing_ranges:
        earliest_date = session.execute(
            select(func.min(Price.date)).where(Price.crypto_id == crypto_id)
        ).scalar_one_or_none()
        if earliest_date:
            fallback_end = earliest_date - timedelta(days=1)
            if fallback_end >= min_allowed_date:
                start_date, end_date = build_window(fallback_end)
                existing_dates = fetch_existing_dates(start_date, end_date)
                missing_ranges = _compute_missing_ranges(
                    start_date, end_date, existing_dates
                )

    if not missing_ranges:
        return {"inserted": 0, "requested": 0, "ranges": []}

    inserted_total = 0
    requested = 0
    ranges_info: list[dict[str, str]] = []

    request_ranges: list[tuple[date, date]] = []
    for range_start, range_end in missing_ranges:
        request_ranges.extend(
            _split_date_range(range_start, range_end, max_chunk_days)
        )

    for idx, (range_start, range_end) in enumerate(request_ranges):
        from_ts = _to_timestamp(range_start, end_of_day=False)
        to_ts = _to_timestamp(range_end, end_of_day=True)
        payload = client.get_market_chart_range(
            crypto.coingecko_id, vs_currency, from_ts, to_ts
        )
        prices = payload.get("prices", [])
        if prices:
            by_date: dict[date, Decimal] = {}
            for timestamp_ms, price in prices:
                dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).date()
                if dt in existing_dates:
                    continue
                by_date[dt] = Decimal(str(price))

            if by_date:
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
                inserted_total += len(records)
                existing_dates.update(by_date.keys())

        requested += 1
        ranges_info.append(
            {
                "from": range_start.isoformat(),
                "to": range_end.isoformat(),
            }
        )
        if idx < len(request_ranges) - 1 and request_delay > 0:
            time_module.sleep(request_delay)

    return {"inserted": inserted_total, "requested": requested, "ranges": ranges_info}


def update_daily_prices(
    client: CoinGeckoClient,
    vs_currency: str,
    as_of: date | None = None,
    request_delay: float = 0.0,
) -> dict[str, Any]:
    session = get_session()
    today = date.today()
    as_of = as_of or today
    if as_of >= today:
        as_of = today - timedelta(days=1)

    cryptos = session.execute(select(Cryptocurrency)).scalars().all()
    if not cryptos:
        return {"updated": 0, "skipped": 0, "errors": []}
    updated = 0
    skipped = 0
    errors: list[dict[str, str]] = []

    for idx, crypto in enumerate(cryptos):
        should_request = not _price_exists(session, crypto.id, as_of)
        if not should_request:
            skipped += 1
            continue
        try:
            did_update = update_crypto_price(session, client, crypto, vs_currency, as_of)
            if did_update:
                updated += 1
            else:
                skipped += 1
        except Exception as exc:
            session.rollback()
            errors.append({"crypto_id": str(crypto.id), "error": str(exc)})
        finally:
            if should_request and request_delay > 0 and idx < len(cryptos) - 1:
                time_module.sleep(request_delay)

    return {"updated": updated, "skipped": skipped, "errors": errors}
