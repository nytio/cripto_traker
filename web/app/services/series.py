from datetime import date, timedelta

from sqlalchemy import select

from ..models import Price


def clamp_days(days_raw: str, max_days: int) -> int:
    days = int(days_raw) if days_raw.isdigit() else 0
    if days > max_days:
        return max_days
    return days


def fetch_price_series(session, crypto_id: int, days: int) -> list[dict[str, object]]:
    query = select(Price.date, Price.price).where(Price.crypto_id == crypto_id)
    if days > 0:
        start_date = date.today() - timedelta(days=days)
        query = query.where(Price.date >= start_date)
    query = query.order_by(Price.date.asc())

    rows = session.execute(query).mappings().all()
    return [{"date": row["date"], "price": float(row["price"])} for row in rows]
