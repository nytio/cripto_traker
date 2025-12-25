from datetime import date, timedelta

from flask import Blueprint, abort, current_app, render_template, request
from sqlalchemy import select

from ..db import get_session
from ..models import Cryptocurrency
from ..services.analytics import compute_indicators, compute_prophet_forecast
from ..services.series import clamp_days, fetch_price_series

bp = Blueprint("charts", __name__)


@bp.get("/cryptos/<int:crypto_id>")
def crypto_detail(crypto_id: int):
    session = get_session()
    crypto = session.execute(
        select(Cryptocurrency).where(Cryptocurrency.id == crypto_id)
    ).scalar_one_or_none()
    if not crypto:
        abort(404)

    max_days = current_app.config["MAX_HISTORY_DAYS"]
    days = clamp_days(request.args.get("days", "").strip(), max_days)

    all_rows = fetch_price_series(session, crypto_id, 0)
    if days > 0:
        start_date = date.today() - timedelta(days=days)
        rows = [row for row in all_rows if row["date"] >= start_date]
    else:
        start_date = None
        rows = all_rows
    series = compute_indicators(rows)
    forecast_days = current_app.config.get("PROPHET_FUTURE_DAYS", 30)
    forecast = compute_prophet_forecast(all_rows, forecast_days)
    if start_date is not None:
        forecast = [
            row
            for row in forecast
            if date.fromisoformat(row["date"]) >= start_date
        ]
    return render_template(
        "crypto_detail.html",
        crypto=crypto,
        series=series,
        prophet_forecast=forecast,
        today=date.today().isoformat(),
        currency=current_app.config["COINGECKO_VS_CURRENCY"].upper(),
        days=days,
        max_days=max_days,
    )
