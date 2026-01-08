from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import select

from ..db import get_session
from ..models import Cryptocurrency, Price, ProphetForecast, UserCrypto
from ..services.analytics import compute_indicators
from ..services.jobs import get_job_status, start_job
from ..services.prophet import store_prophet_forecast
from ..services.prophet_defaults import resolve_prophet_defaults
from ..services.series import fetch_price_series

bp = Blueprint("dashboard", __name__)

PROPHET_BULK_JOB_TYPE = "prophet_bulk"
PROPHET_BULK_LABEL = "Prophet (all)"


def _prophet_bulk_job_key(user_id: int) -> str:
    return f"{PROPHET_BULK_JOB_TYPE}:{user_id}"


def _dashboard_job_response(job: dict[str, object]):
    accept_header = request.headers.get("Accept", "")
    if "application/json" in accept_header:
        status_code = 202 if job.get("state") == "running" else 200
        return jsonify(job), status_code

    state = job.get("state")
    message = job.get("message") or "Update queued."
    if state == "done":
        flash(message, "success")
    elif state in {"error"}:
        flash(message, "error")
    elif state == "busy":
        flash(message, "warning")
    else:
        flash(message, "info")
    return redirect(url_for("dashboard.index"))


def _latest_bollinger_indicators(
    recent_prices: list[Price], latest_price: Price | None
):
    result = {"percent": None, "bandwidth": None, "sma_spread": None}
    if latest_price is None:
        return result
    if len(recent_prices) < 20:
        return result
    rows = [
        {"date": price.date, "price": float(price.price)}
        for price in reversed(recent_prices)
    ]
    indicators = compute_indicators(rows)
    if not indicators:
        return result
    latest = indicators[-1]
    bb_upper = latest.get("bb_upper")
    bb_lower = latest.get("bb_lower")
    if bb_upper is None or bb_lower is None:
        return result
    band = bb_upper - bb_lower
    if not band:
        return result
    sma_20 = latest.get("sma_20")
    if sma_20 is None or not sma_20:
        bandwidth = None
    else:
        bandwidth = band / sma_20
    result["percent"] = (float(latest_price.price) - bb_lower) / band
    result["bandwidth"] = bandwidth
    if len(recent_prices) >= 50:
        sma_50 = latest.get("sma_50")
        if sma_20 is not None and sma_50 is not None and sma_50:
            result["sma_spread"] = (sma_20 - sma_50) / sma_50
    return result


def _latest_prophet_percent(
    session, crypto_id: int, latest_price: Price | None
):
    if latest_price is None:
        return None
    prophet_yhat = (
        session.execute(
            select(ProphetForecast.yhat)
            .where(ProphetForecast.crypto_id == crypto_id)
            .order_by(ProphetForecast.date.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if prophet_yhat is None:
        return None
    price_value = float(latest_price.price)
    if not price_value:
        return None
    return (float(prophet_yhat) - price_value) / price_value


@bp.get("/")
def index():
    session = get_session()
    cryptos = (
        session.execute(
            select(Cryptocurrency)
            .join(UserCrypto, UserCrypto.crypto_id == Cryptocurrency.id)
            .where(UserCrypto.user_id == g.user.id)
            .order_by(Cryptocurrency.name)
        )
        .scalars()
        .all()
    )
    rows = []
    for crypto in cryptos:
        recent_prices = (
            session.execute(
                select(Price)
                .where(Price.crypto_id == crypto.id)
                .order_by(Price.date.desc())
                .limit(50)
            )
            .scalars()
            .all()
        )
        latest_price = recent_prices[0] if recent_prices else None
        bollinger = _latest_bollinger_indicators(recent_prices, latest_price)
        rows.append(
            {
                "crypto": crypto,
                "latest": latest_price,
                "bollinger_percent": bollinger["percent"],
                "bollinger_bandwidth": bollinger["bandwidth"],
                "sma_spread": bollinger["sma_spread"],
                "prophet_percent": _latest_prophet_percent(
                    session, crypto.id, latest_price
                ),
            }
        )

    currency = current_app.config["COINGECKO_VS_CURRENCY"].upper()
    return render_template("dashboard.html", rows=rows, currency=currency)


@bp.post("/prophet/bulk")
def recalculate_prophet_bulk():
    job_type = PROPHET_BULK_JOB_TYPE
    horizon_days = current_app.config.get("PROPHET_FUTURE_DAYS", 30)
    if horizon_days <= 0:
        job = {
            "job_key": _prophet_bulk_job_key(g.user.id),
            "job_type": job_type,
            "label": PROPHET_BULK_LABEL,
            "state": "error",
            "message": "Prophet forecast disabled",
        }
        return _dashboard_job_response(job)

    session = get_session()
    crypto_ids = (
        session.execute(
            select(Cryptocurrency.id)
            .join(UserCrypto, UserCrypto.crypto_id == Cryptocurrency.id)
            .where(UserCrypto.user_id == g.user.id)
        )
        .scalars()
        .all()
    )
    if not crypto_ids:
        job = {
            "job_key": _prophet_bulk_job_key(g.user.id),
            "job_type": job_type,
            "label": PROPHET_BULK_LABEL,
            "state": "error",
            "message": "No assets to update.",
        }
        return _dashboard_job_response(job)

    max_days = current_app.config["MAX_HISTORY_DAYS"]
    defaults = resolve_prophet_defaults(None, max_days)
    prophet_days = int(defaults["days"])
    yearly_raw = str(defaults["yearly"])
    if yearly_raw == "false":
        yearly_seasonality: bool | str = False
    elif yearly_raw == "auto":
        yearly_seasonality = "auto"
    else:
        yearly_seasonality = True
    changepoint_scale = float(defaults["changepoint"])
    seasonality_scale = float(defaults["seasonality"])
    changepoint_range = float(defaults["changepoint_range"])
    job_key = _prophet_bulk_job_key(g.user.id)

    def run_prophet_bulk():
        job_session = get_session()
        total_points = 0
        try:
            for crypto_id in crypto_ids:
                rows = fetch_price_series(job_session, crypto_id, prophet_days)
                if len(rows) < 2:
                    # Drop ORM state between cryptos to keep memory flat in bulk runs.
                    job_session.expunge_all()
                    continue
                stored = store_prophet_forecast(
                    job_session,
                    crypto_id,
                    rows,
                    horizon_days,
                    yearly_seasonality=yearly_seasonality,
                    changepoint_prior_scale=changepoint_scale,
                    seasonality_prior_scale=seasonality_scale,
                    changepoint_range=changepoint_range,
                )
                total_points += stored
                job_session.expunge_all()
            if total_points <= 0:
                raise RuntimeError("Prophet forecast not available")
            return total_points
        finally:
            job_session.close()

    job = start_job(job_key, job_type, PROPHET_BULK_LABEL, run_prophet_bulk)
    return _dashboard_job_response(job)


@bp.get("/jobs/prophet-bulk")
def prophet_bulk_status():
    job_key = _prophet_bulk_job_key(g.user.id)
    job = get_job_status(job_key, PROPHET_BULK_JOB_TYPE, PROPHET_BULK_LABEL)
    return jsonify(job)
