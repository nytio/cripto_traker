from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import time as time_module
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import func, select

from ..db import get_session
from ..models import Cryptocurrency, Price
from .coingecko import CoinGeckoClient, CoinGeckoError
from .coincap import CoincapClient, CoincapError

MAX_HISTORY_DAYS_DEFAULT = 3650
MAX_BACKFILL_CHUNK_DAYS = 365
COINGECKO_DAILY_LIMIT_DAYS = 365


def load_historical_prices(
    client: CoinGeckoClient,
    crypto: Cryptocurrency,
    vs_currency: str,
    days: int,
    request_delay: float = 1.1,
    max_history_days: int | None = None,
    max_request_days: int | None = None,
    coincap_client: CoincapClient | None = None,
    coincap_request_delay: float | None = None,
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
        coincap_client=coincap_client,
        coincap_request_delay=coincap_request_delay,
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
    session,
    client: CoinGeckoClient,
    crypto: Cryptocurrency,
    vs_currency: str,
    as_of: date,
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
    crypto_id: int,
    client: CoinGeckoClient,
    vs_currency: str,
    as_of: date | None = None,
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


def _to_timestamp_ms(day: date, end_of_day: bool) -> int:
    return _to_timestamp(day, end_of_day) * 1000


def _fetch_historical_price_coingecko(
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


def _fetch_historical_price(
    client: CoinGeckoClient,
    coingecko_id: str,
    vs_currency: str,
    as_of: date,
) -> Decimal:
    return _fetch_historical_price_coingecko(client, coingecko_id, vs_currency, as_of)


def _fetch_daily_prices_range_coingecko(
    client: CoinGeckoClient,
    coingecko_id: str,
    vs_currency: str,
    start_date: date,
    end_date: date,
) -> dict[date, Decimal]:
    from_ts = _to_timestamp(start_date, end_of_day=False)
    to_ts = _to_timestamp(end_date, end_of_day=True)
    payload = client.get_market_chart_range(coingecko_id, vs_currency, from_ts, to_ts)
    prices = payload.get("prices", [])
    if not prices:
        return {}
    by_date: dict[date, Decimal] = {}
    for timestamp_ms, price in sorted(prices, key=lambda item: item[0]):
        if price is None:
            continue
        dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).date()
        if dt < start_date or dt > end_date:
            continue
        by_date[dt] = Decimal(str(price))
    return by_date


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


def _split_ranges_by_boundary(
    ranges: list[tuple[date, date]], boundary: date
) -> tuple[list[tuple[date, date]], list[tuple[date, date]]]:
    historical: list[tuple[date, date]] = []
    recent: list[tuple[date, date]] = []
    for range_start, range_end in ranges:
        if range_end < boundary:
            historical.append((range_start, range_end))
        elif range_start >= boundary:
            recent.append((range_start, range_end))
        else:
            historical.append((range_start, boundary - timedelta(days=1)))
            recent.append((boundary, range_end))
    return historical, recent


def backfill_historical_prices(
    crypto_id: int,
    client: CoinGeckoClient,
    vs_currency: str,
    days: int,
    request_delay: float = 1.1,
    max_history_days: int | None = None,
    max_request_days: int | None = None,
    coincap_client: CoincapClient | None = None,
    coincap_request_delay: float | None = None,
) -> dict[str, Any]:
    session = get_session()
    today = date.today()
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

    crypto = session.execute(
        select(Cryptocurrency).where(Cryptocurrency.id == crypto_id)
    ).scalar_one_or_none()
    if not crypto:
        raise ValueError("Crypto not found")

    latest_date = session.execute(
        select(func.max(Price.date)).where(Price.crypto_id == crypto_id)
    ).scalar_one_or_none()
    earliest_date = session.execute(
        select(func.min(Price.date)).where(Price.crypto_id == crypto_id)
    ).scalar_one_or_none()

    anchor_latest = latest_date or (today - timedelta(days=1))
    min_allowed_date = anchor_latest - timedelta(days=max_days - 1)
    if earliest_date:
        end_date = earliest_date - timedelta(days=1)
    else:
        end_date = min(today - timedelta(days=1), anchor_latest)
    if end_date < min_allowed_date:
        return {"inserted": 0, "requested": 0, "ranges": []}

    start_date = end_date - timedelta(days=days - 1)
    if start_date < min_allowed_date:
        start_date = min_allowed_date

    def fetch_existing_dates(start: date, end: date) -> set[date]:
        rows = session.execute(
            select(Price.date)
            .where(Price.crypto_id == crypto_id)
            .where(Price.date >= start)
            .where(Price.date <= end)
        ).all()
        return {row[0] for row in rows}

    existing_dates = fetch_existing_dates(start_date, end_date)
    missing_ranges = _compute_missing_ranges(start_date, end_date, existing_dates)

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

    if not coincap_client:
        raise CoincapError("Coincap client required for backfill")
    if vs_currency.lower() != "usd":
        raise CoincapError("Coincap only supports USD historical prices")
    if coincap_request_delay is None:
        coincap_request_delay = request_delay

    def persist_prices(by_date: dict[date, Decimal]) -> int:
        if not by_date:
            return 0
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
        existing_dates.update(by_date.keys())
        return len(records)

    for idx, (range_start, range_end) in enumerate(request_ranges):
        from_ts = _to_timestamp_ms(range_start, end_of_day=False)
        to_ts = _to_timestamp_ms(range_end, end_of_day=True)
        payload = coincap_client.get_asset_history(
            crypto.coingecko_id, from_ts, to_ts, interval="d1"
        )
        data = payload.get("data", [])
        if data:
            by_date: dict[date, Decimal] = {}
            for entry in data:
                timestamp_ms = entry.get("time")
                price = entry.get("priceUsd")
                if timestamp_ms is None or price is None:
                    continue
                dt = datetime.fromtimestamp(
                    timestamp_ms / 1000, tz=timezone.utc
                ).date()
                if dt < range_start or dt > range_end:
                    continue
                if dt in existing_dates:
                    continue
                by_date[dt] = Decimal(str(price))
            inserted_total += persist_prices(by_date)

        requested += 1
        ranges_info.append(
            {
                "from": range_start.isoformat(),
                "to": range_end.isoformat(),
            }
        )
        if idx < len(request_ranges) - 1 and coincap_request_delay > 0:
            time_module.sleep(coincap_request_delay)

    return {"inserted": inserted_total, "requested": requested, "ranges": ranges_info}


def _load_missing_price_info(session, crypto_id: int) -> dict[str, Any]:
    crypto = session.execute(
        select(Cryptocurrency).where(Cryptocurrency.id == crypto_id)
    ).scalar_one_or_none()
    if not crypto:
        raise ValueError("Crypto not found")

    start_date = session.execute(
        select(func.min(Price.date)).where(Price.crypto_id == crypto_id)
    ).scalar_one_or_none()
    end_date = session.execute(
        select(func.max(Price.date)).where(Price.crypto_id == crypto_id)
    ).scalar_one_or_none()
    if not start_date or not end_date:
        return {
            "crypto": crypto,
            "has_history": False,
            "missing_ranges": [],
            "missing_dates": [],
            "existing_dates": set(),
            "start_date": None,
            "end_date": None,
            "total_days": 0,
            "stored_days": 0,
        }

    rows = session.execute(
        select(Price.date)
        .where(Price.crypto_id == crypto_id)
        .where(Price.date >= start_date)
        .where(Price.date <= end_date)
    ).all()
    existing_dates = {row[0] for row in rows}
    missing_ranges = _compute_missing_ranges(start_date, end_date, existing_dates)
    missing_dates: list[date] = []
    for range_start, range_end in missing_ranges:
        current = range_start
        while current <= range_end:
            missing_dates.append(current)
            current += timedelta(days=1)

    total_days = (end_date - start_date).days + 1
    stored_days = len(existing_dates)

    return {
        "crypto": crypto,
        "has_history": True,
        "missing_ranges": missing_ranges,
        "missing_dates": missing_dates,
        "existing_dates": existing_dates,
        "start_date": start_date,
        "end_date": end_date,
        "total_days": total_days,
        "stored_days": stored_days,
    }


def inspect_missing_prices(crypto_id: int) -> dict[str, Any]:
    session = get_session()
    info = _load_missing_price_info(session, crypto_id)
    return {
        "has_history": info["has_history"],
        "missing_ranges": info["missing_ranges"],
        "missing_dates": info["missing_dates"],
        "start_date": info["start_date"],
        "end_date": info["end_date"],
        "total_days": info["total_days"],
        "stored_days": info["stored_days"],
    }


def fill_missing_prices(
    crypto_id: int,
    vs_currency: str,
    request_delay: float = 1.1,
    max_request_days: int | None = None,
    coincap_client: CoincapClient | None = None,
    coincap_request_delay: float | None = None,
) -> dict[str, Any]:
    session = get_session()
    info = _load_missing_price_info(session, crypto_id)
    crypto = info["crypto"]
    missing_ranges = info["missing_ranges"]
    existing_dates = info["existing_dates"]
    if not info["has_history"]:
        return {"inserted": 0, "requested": 0, "ranges": [], "has_history": False}
    if not missing_ranges:
        return {"inserted": 0, "requested": 0, "ranges": [], "has_history": True}

    if not coincap_client:
        raise CoincapError("Coincap client required to verify history")
    if vs_currency.lower() != "usd":
        raise CoincapError("Coincap only supports USD historical prices")
    if coincap_request_delay is None:
        coincap_request_delay = request_delay

    max_chunk_days = (
        max_request_days if max_request_days is not None else MAX_BACKFILL_CHUNK_DAYS
    )

    request_ranges: list[tuple[date, date]] = []
    for range_start, range_end in missing_ranges:
        request_ranges.extend(
            _split_date_range(range_start, range_end, max_chunk_days)
        )

    inserted_total = 0
    requested = 0
    ranges_info: list[dict[str, str]] = []

    def persist_prices(by_date: dict[date, Decimal]) -> int:
        if not by_date:
            return 0
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
        existing_dates.update(by_date.keys())
        return len(records)

    for idx, (range_start, range_end) in enumerate(request_ranges):
        from_ts = _to_timestamp_ms(range_start, end_of_day=False)
        to_ts = _to_timestamp_ms(range_end, end_of_day=True)
        payload = coincap_client.get_asset_history(
            crypto.coingecko_id, from_ts, to_ts, interval="d1"
        )
        data = payload.get("data", [])
        if data:
            by_date: dict[date, Decimal] = {}
            for entry in data:
                timestamp_ms = entry.get("time")
                price = entry.get("priceUsd")
                if timestamp_ms is None or price is None:
                    continue
                dt = datetime.fromtimestamp(
                    timestamp_ms / 1000, tz=timezone.utc
                ).date()
                if dt < range_start or dt > range_end:
                    continue
                if dt in existing_dates:
                    continue
                by_date[dt] = Decimal(str(price))
            inserted_total += persist_prices(by_date)

        requested += 1
        ranges_info.append(
            {
                "from": range_start.isoformat(),
                "to": range_end.isoformat(),
            }
        )
        if idx < len(request_ranges) - 1 and coincap_request_delay > 0:
            time_module.sleep(coincap_request_delay)

    return {
        "inserted": inserted_total,
        "requested": requested,
        "ranges": ranges_info,
        "has_history": True,
    }


def update_daily_prices(
    client: CoinGeckoClient,
    vs_currency: str,
    as_of: date | None = None,
    request_delay: float = 0.0,
    crypto_ids: list[int] | None = None,
) -> dict[str, Any]:
    session = get_session()
    today = date.today()
    end_date = as_of or today
    if end_date >= today:
        end_date = today - timedelta(days=1)

    if crypto_ids is None:
        cryptos = session.execute(select(Cryptocurrency)).scalars().all()
    elif not crypto_ids:
        cryptos = []
    else:
        cryptos = (
            session.execute(
                select(Cryptocurrency).where(Cryptocurrency.id.in_(crypto_ids))
            )
            .scalars()
            .all()
        )
    if not cryptos:
        return {"updated": 0, "skipped": 0, "errors": [], "inserted": 0}
    updated = 0
    skipped = 0
    inserted_total = 0
    errors: list[dict[str, str]] = []

    for idx, crypto in enumerate(cryptos):
        latest_date = session.execute(
            select(func.max(Price.date)).where(Price.crypto_id == crypto.id)
        ).scalar_one_or_none()
        if latest_date:
            range_start = latest_date + timedelta(days=1)
        else:
            range_start = end_date
        if range_start > end_date:
            skipped += 1
            continue
        missing_days = (end_date - range_start).days + 1
        if missing_days > COINGECKO_DAILY_LIMIT_DAYS:
            errors.append(
                {
                    "crypto_id": str(crypto.id),
                    "error": (
                        f"Missing range {missing_days} days exceeds "
                        f"{COINGECKO_DAILY_LIMIT_DAYS} day limit"
                    ),
                }
            )
            continue
        try:
            by_date = _fetch_daily_prices_range_coingecko(
                client, crypto.coingecko_id, vs_currency, range_start, end_date
            )
            if not by_date:
                skipped += 1
                continue
            records = [
                Price(crypto_id=crypto.id, date=day, price=price)
                for day, price in sorted(by_date.items())
            ]
            session.add_all(records)
            session.commit()
            inserted_total += len(records)
            updated += 1
        except Exception as exc:
            session.rollback()
            errors.append({"crypto_id": str(crypto.id), "error": str(exc)})
        finally:
            if request_delay > 0 and idx < len(cryptos) - 1:
                time_module.sleep(request_delay)

    return {
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "inserted": inserted_total,
    }
