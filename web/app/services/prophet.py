from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select

from ..models import ProphetForecast
from .analytics import compute_prophet_forecast


def _to_decimal(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def store_prophet_forecast(
    session,
    crypto_id: int,
    rows: list[dict[str, Any]],
    horizon_days: int,
) -> int:
    if horizon_days <= 0 or len(rows) < 2:
        return 0
    cutoff_date = rows[-1]["date"]
    forecast = compute_prophet_forecast(rows, horizon_days)
    if not forecast:
        return 0

    session.execute(
        delete(ProphetForecast).where(ProphetForecast.crypto_id == crypto_id)
    )

    records = []
    for row in forecast:
        row_date = date.fromisoformat(row["date"])
        records.append(
            ProphetForecast(
                crypto_id=crypto_id,
                date=row_date,
                yhat=_to_decimal(row.get("yhat")),
                yhat_lower=_to_decimal(row.get("yhat_lower")),
                yhat_upper=_to_decimal(row.get("yhat_upper")),
                cutoff_date=cutoff_date,
                horizon_days=horizon_days,
            )
        )

    session.add_all(records)
    session.commit()
    return len(records)


def fetch_prophet_forecast(
    session, crypto_id: int, start_date: date | None
) -> list[dict[str, Any]]:
    stmt = select(ProphetForecast).where(ProphetForecast.crypto_id == crypto_id)
    if start_date is not None:
        stmt = stmt.where(ProphetForecast.date >= start_date)
    stmt = stmt.order_by(ProphetForecast.date.asc())
    rows = session.execute(stmt).scalars().all()

    return [
        {
            "date": row.date.isoformat(),
            "yhat": float(row.yhat) if row.yhat is not None else None,
            "yhat_lower": float(row.yhat_lower) if row.yhat_lower is not None else None,
            "yhat_upper": float(row.yhat_upper) if row.yhat_upper is not None else None,
        }
        for row in rows
    ]


def fetch_prophet_meta(session, crypto_id: int) -> tuple[date | None, int | None]:
    row = session.execute(
        select(ProphetForecast.cutoff_date, ProphetForecast.horizon_days)
        .where(ProphetForecast.crypto_id == crypto_id)
        .order_by(ProphetForecast.created_at.desc())
        .limit(1)
    ).first()
    if not row:
        return None, None
    return row[0], row[1]
