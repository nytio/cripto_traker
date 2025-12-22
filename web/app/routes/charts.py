from datetime import date, timedelta

from flask import Blueprint, abort, current_app, render_template, request
from sqlalchemy import select

from ..db import get_session
from ..models import Cryptocurrency, Price
from ..services.analytics import compute_indicators

bp = Blueprint("charts", __name__)


@bp.get("/cryptos/<int:crypto_id>")
def crypto_detail(crypto_id: int):
    session = get_session()
    crypto = session.execute(
        select(Cryptocurrency).where(Cryptocurrency.id == crypto_id)
    ).scalar_one_or_none()
    if not crypto:
        abort(404)

    days_raw = request.args.get("days", "").strip()
    days = int(days_raw) if days_raw.isdigit() else 0
    max_days = current_app.config["MAX_HISTORY_DAYS"]
    if days > max_days:
        days = max_days

    query = select(Price).where(Price.crypto_id == crypto_id)
    if days > 0:
        start_date = date.today() - timedelta(days=days)
        query = query.where(Price.date >= start_date)
    query = query.order_by(Price.date.asc())

    prices = session.execute(query).scalars().all()

    rows = [
        {"date": price.date, "price": float(price.price)} for price in prices
    ]
    series = compute_indicators(rows)
    return render_template(
        "crypto_detail.html",
        crypto=crypto,
        series=series,
        currency=current_app.config["COINGECKO_VS_CURRENCY"].upper(),
        days=days,
        max_days=max_days,
    )
