from datetime import date, timedelta

from flask import (
    Blueprint,
    abort,
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

from ..auth_utils import require_user_crypto
from ..db import get_session
from ..models import Cryptocurrency
from ..services.analytics import compute_indicators
from ..services.prophet import (
    fetch_prophet_forecast,
    fetch_prophet_meta,
    store_prophet_forecast,
)
from ..services.rnn import (
    fetch_gru_forecast,
    fetch_gru_meta,
    fetch_lstm_forecast,
    fetch_lstm_meta,
    store_gru_forecast,
    store_lstm_forecast,
)
from ..services.jobs import get_job_status, start_job
from ..services.series import clamp_days, fetch_price_series

bp = Blueprint("charts", __name__)

JOB_LABELS = {
    "prophet": "Prophet",
    "lstm": "LSTM",
    "gru": "GRU",
}


def _redirect_with_days(crypto_id: int):
    days_raw = request.form.get("range_days", "").strip()
    if not days_raw:
        days_raw = request.args.get("days", "").strip()
    if days_raw.isdigit():
        return redirect(
            url_for("charts.crypto_detail", crypto_id=crypto_id, days=days_raw)
        )
    return redirect(url_for("charts.crypto_detail", crypto_id=crypto_id))


def _job_key(job_type: str, crypto_id: int) -> str:
    return f"{job_type}:{crypto_id}"


def _job_response(crypto_id: int, job: dict[str, object]):
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
    return _redirect_with_days(crypto_id)


def _parse_int(
    value: str | None, default: int, allowed: set[int] | None = None
) -> int:
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    if allowed is not None and parsed not in allowed:
        return default
    return parsed


@bp.get("/cryptos/<int:crypto_id>")
def crypto_detail(crypto_id: int):
    session = get_session()
    if not require_user_crypto(session, g.user.id, crypto_id):
        abort(404)
    crypto = session.execute(
        select(Cryptocurrency).where(Cryptocurrency.id == crypto_id)
    ).scalar_one_or_none()
    if not crypto:
        abort(404)

    max_days = current_app.config["MAX_HISTORY_DAYS"]
    backfill_max_days = min(365, max_days)
    days_raw = request.args.get("days", "").strip()
    if not days_raw:
        days_raw = str(min(365, max_days))
    days = clamp_days(days_raw, max_days)

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

    lstm_forecast = fetch_lstm_forecast(session, crypto_id, start_date)
    lstm_cutoff_date, _lstm_horizon_days = fetch_lstm_meta(
        session, crypto_id
    )
    lstm_line_date = (
        lstm_cutoff_date.isoformat() if lstm_cutoff_date else None
    )

    gru_forecast = fetch_gru_forecast(session, crypto_id, start_date)
    gru_cutoff_date, _gru_horizon_days = fetch_gru_meta(
        session, crypto_id
    )
    gru_line_date = gru_cutoff_date.isoformat() if gru_cutoff_date else None
    return render_template(
        "crypto_detail.html",
        crypto=crypto,
        series=series,
        prophet_forecast=prophet_forecast,
        prophet_cutoff=prophet_cutoff_date.isoformat()
        if prophet_cutoff_date
        else None,
        prophet_line_date=prophet_line_date,
        lstm_forecast=lstm_forecast,
        lstm_cutoff=lstm_cutoff_date.isoformat() if lstm_cutoff_date else None,
        lstm_line_date=lstm_line_date,
        gru_forecast=gru_forecast,
        gru_cutoff=gru_cutoff_date.isoformat() if gru_cutoff_date else None,
        gru_line_date=gru_line_date,
        currency=current_app.config["COINGECKO_VS_CURRENCY"].upper(),
        days=days,
        max_days=max_days,
        backfill_max_days=backfill_max_days,
    )


@bp.post("/cryptos/<int:crypto_id>/prophet")
def recalculate_prophet(crypto_id: int):
    session = get_session()
    if not require_user_crypto(session, g.user.id, crypto_id):
        abort(404)
    crypto = session.execute(
        select(Cryptocurrency).where(Cryptocurrency.id == crypto_id)
    ).scalar_one_or_none()
    if not crypto:
        abort(404)

    job_type = "prophet"
    horizon_days = current_app.config.get("PROPHET_FUTURE_DAYS", 30)
    if horizon_days <= 0:
        job = {
            "job_key": _job_key(job_type, crypto_id),
            "job_type": job_type,
            "label": JOB_LABELS[job_type],
            "state": "error",
            "message": "Prophet forecast disabled",
        }
        return _job_response(crypto_id, job)
    max_days = current_app.config["MAX_HISTORY_DAYS"]
    prophet_days_raw = request.form.get("prophet_days", "").strip()
    prophet_days = clamp_days(prophet_days_raw, max_days)
    job_key = _job_key(job_type, crypto_id)

    def run_prophet():
        job_session = get_session()
        try:
            rows = fetch_price_series(job_session, crypto_id, prophet_days)
            if len(rows) < 2:
                raise ValueError("Not enough price history for Prophet")
            stored = store_prophet_forecast(
                job_session, crypto_id, rows, horizon_days
            )
            if not stored:
                raise RuntimeError("Prophet forecast not available")
            return stored
        finally:
            job_session.close()

    job = start_job(job_key, job_type, JOB_LABELS[job_type], run_prophet)
    return _job_response(crypto_id, job)


@bp.post("/cryptos/<int:crypto_id>/lstm")
def recalculate_lstm(crypto_id: int):
    session = get_session()
    if not require_user_crypto(session, g.user.id, crypto_id):
        abort(404)
    crypto = session.execute(
        select(Cryptocurrency).where(Cryptocurrency.id == crypto_id)
    ).scalar_one_or_none()
    if not crypto:
        abort(404)

    job_type = "lstm"
    horizon_days = current_app.config.get("RNN_FUTURE_DAYS", 30)
    if horizon_days <= 0:
        job = {
            "job_key": _job_key(job_type, crypto_id),
            "job_type": job_type,
            "label": JOB_LABELS[job_type],
            "state": "error",
            "message": "LSTM forecast disabled",
        }
        return _job_response(crypto_id, job)

    max_days = current_app.config["MAX_HISTORY_DAYS"]
    lstm_days_raw = request.form.get("lstm_days", "").strip()
    lstm_days = clamp_days(lstm_days_raw, max_days)
    lstm_layers = _parse_int(
        request.form.get("lstm_layers"),
        1,
        allowed={1, 2, 3},
    )
    lstm_output_chunk = _parse_int(
        request.form.get("lstm_output_chunk"),
        1,
        allowed={1, 2, 3},
    )
    job_key = _job_key(job_type, crypto_id)

    def run_lstm():
        job_session = get_session()
        try:
            rows = fetch_price_series(job_session, crypto_id, lstm_days)
            if len(rows) < 5:
                raise ValueError("Not enough price history for LSTM")
            stored = store_lstm_forecast(
                job_session,
                crypto_id,
                rows,
                horizon_days,
                n_rnn_layers=lstm_layers,
                output_chunk_length=lstm_output_chunk,
            )
            if not stored:
                raise RuntimeError("LSTM forecast not available")
            return stored
        finally:
            job_session.close()

    job = start_job(job_key, job_type, JOB_LABELS[job_type], run_lstm)
    return _job_response(crypto_id, job)


@bp.post("/cryptos/<int:crypto_id>/gru")
def recalculate_gru(crypto_id: int):
    session = get_session()
    if not require_user_crypto(session, g.user.id, crypto_id):
        abort(404)
    crypto = session.execute(
        select(Cryptocurrency).where(Cryptocurrency.id == crypto_id)
    ).scalar_one_or_none()
    if not crypto:
        abort(404)

    job_type = "gru"
    horizon_days = current_app.config.get("RNN_FUTURE_DAYS", 30)
    if horizon_days <= 0:
        job = {
            "job_key": _job_key(job_type, crypto_id),
            "job_type": job_type,
            "label": JOB_LABELS[job_type],
            "state": "error",
            "message": "GRU forecast disabled",
        }
        return _job_response(crypto_id, job)

    max_days = current_app.config["MAX_HISTORY_DAYS"]
    gru_days_raw = request.form.get("gru_days", "").strip()
    gru_days = clamp_days(gru_days_raw, max_days)
    gru_layers = _parse_int(
        request.form.get("gru_layers"),
        1,
        allowed={1, 2, 3},
    )
    gru_output_chunk = _parse_int(
        request.form.get("gru_output_chunk"),
        1,
        allowed={1, 2, 3},
    )
    job_key = _job_key(job_type, crypto_id)

    def run_gru():
        job_session = get_session()
        try:
            rows = fetch_price_series(job_session, crypto_id, gru_days)
            if len(rows) < 5:
                raise ValueError("Not enough price history for GRU")
            stored = store_gru_forecast(
                job_session,
                crypto_id,
                rows,
                horizon_days,
                n_rnn_layers=gru_layers,
                output_chunk_length=gru_output_chunk,
            )
            if not stored:
                raise RuntimeError("GRU forecast not available")
            return stored
        finally:
            job_session.close()

    job = start_job(job_key, job_type, JOB_LABELS[job_type], run_gru)
    return _job_response(crypto_id, job)


@bp.get("/cryptos/<int:crypto_id>/jobs/<string:job_type>")
def job_status(crypto_id: int, job_type: str):
    if job_type not in JOB_LABELS:
        abort(404)
    session = get_session()
    if not require_user_crypto(session, g.user.id, crypto_id):
        abort(404)
    job_key = _job_key(job_type, crypto_id)
    job = get_job_status(job_key, job_type, JOB_LABELS[job_type])
    return jsonify(job)
