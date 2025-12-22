from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import and_, func, select

from ..db import get_session
from ..models import Cryptocurrency, Price
from ..services.analytics import compute_indicators
from ..services.series import clamp_days, fetch_price_series

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/cryptos")
def list_cryptos():
    session = get_session()
    latest = (
        select(Price.crypto_id, func.max(Price.date).label("max_date"))
        .group_by(Price.crypto_id)
        .subquery()
    )
    stmt = (
        select(Cryptocurrency, Price)
        .outerjoin(latest, latest.c.crypto_id == Cryptocurrency.id)
        .outerjoin(
            Price,
            and_(
                Price.crypto_id == Cryptocurrency.id,
                Price.date == latest.c.max_date,
            ),
        )
        .order_by(Cryptocurrency.name)
    )
    rows = session.execute(stmt).all()
    payload = []
    for crypto, price in rows:
        payload.append(
            {
                "id": crypto.id,
                "coingecko_id": crypto.coingecko_id,
                "name": crypto.name,
                "symbol": crypto.symbol,
                "latest_price": float(price.price) if price else None,
                "latest_date": price.date.isoformat() if price else None,
            }
        )
    return jsonify(payload)


@bp.get("/cryptos/<int:crypto_id>/prices")
def prices(crypto_id: int):
    session = get_session()
    prices = (
        session.execute(
            select(Price)
            .where(Price.crypto_id == crypto_id)
            .order_by(Price.date.asc())
        )
        .scalars()
        .all()
    )
    payload = [
        {"date": price.date.isoformat(), "price": float(price.price)}
        for price in prices
    ]
    return jsonify(payload)


@bp.get("/cryptos/<int:crypto_id>/series")
def series(crypto_id: int):
    session = get_session()
    crypto = session.execute(
        select(Cryptocurrency).where(Cryptocurrency.id == crypto_id)
    ).scalar_one_or_none()
    if not crypto:
        return jsonify({"error": "not found"}), 404

    max_days = current_app.config["MAX_HISTORY_DAYS"]
    days = clamp_days(request.args.get("days", "").strip(), max_days)
    indicators_raw = request.args.get("indicators", "1").strip().lower()
    include_indicators = indicators_raw not in {"0", "false", "no"}

    rows = fetch_price_series(session, crypto_id, days)
    if include_indicators:
        series_data = compute_indicators(rows)
    else:
        series_data = [
            {"date": row["date"].isoformat(), "price": row["price"]} for row in rows
        ]

    return jsonify(
        {
            "crypto_id": crypto_id,
            "coingecko_id": crypto.coingecko_id,
            "currency": current_app.config["COINGECKO_VS_CURRENCY"],
            "days": days,
            "count": len(series_data),
            "series": series_data,
        }
    )
