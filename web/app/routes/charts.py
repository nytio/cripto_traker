from datetime import date, timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import select

from ..db import get_session
from ..models import Cryptocurrency
from ..services.analytics import compute_indicators
from ..services.prophet import (
    fetch_prophet_forecast,
    fetch_prophet_meta,
    store_prophet_forecast,
)
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

    start_date = date.today() - timedelta(days=days) if days > 0 else None
    rows = fetch_price_series(session, crypto_id, days)
    series = compute_indicators(rows)

    prophet_forecast = fetch_prophet_forecast(session, crypto_id, start_date)
    prophet_cutoff_date, _prophet_horizon_days = fetch_prophet_meta(
        session, crypto_id
    )
    prophet_line_date = (
        prophet_cutoff_date.isoformat() if prophet_cutoff_date else None
    )
    return render_template(
        "crypto_detail.html",
        crypto=crypto,
        series=series,
        prophet_forecast=prophet_forecast,
        prophet_cutoff=prophet_cutoff_date.isoformat()
        if prophet_cutoff_date
        else None,
        prophet_line_date=prophet_line_date,
        currency=current_app.config["COINGECKO_VS_CURRENCY"].upper(),
        days=days,
        max_days=max_days,
    )


@bp.post("/cryptos/<int:crypto_id>/prophet")
def recalculate_prophet(crypto_id: int):
    session = get_session()
    crypto = session.execute(
        select(Cryptocurrency).where(Cryptocurrency.id == crypto_id)
    ).scalar_one_or_none()
    if not crypto:
        abort(404)

    horizon_days = current_app.config.get("PROPHET_FUTURE_DAYS", 30)
    if horizon_days <= 0:
        flash("Prophet forecast disabled", "error")
        return redirect(url_for("charts.crypto_detail", crypto_id=crypto_id))
    rows = fetch_price_series(session, crypto_id, 0)
    if len(rows) < 2:
        flash("Not enough price history for Prophet", "error")
        return redirect(url_for("charts.crypto_detail", crypto_id=crypto_id))

    try:
        stored = store_prophet_forecast(session, crypto_id, rows, horizon_days)
    except Exception as exc:
        flash(f"Failed to compute Prophet: {exc}", "error")
        return redirect(url_for("charts.crypto_detail", crypto_id=crypto_id))

    if stored:
        flash(f"Prophet updated: {stored} points", "success")
    else:
        flash("Prophet forecast not available", "error")
    return redirect(url_for("charts.crypto_detail", crypto_id=crypto_id))
