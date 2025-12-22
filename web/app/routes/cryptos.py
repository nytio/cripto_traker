import re

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from ..db import get_session
from ..models import Cryptocurrency
from ..services.coingecko import CoinGeckoClient, CoinGeckoError
from ..services.price_updater import load_historical_prices

bp = Blueprint("cryptos", __name__, url_prefix="/cryptos")

COINGECKO_ID_RE = re.compile(r"^[a-z0-9-]{2,50}$")


@bp.get("/new")
def new_crypto():
    return render_template(
        "cryptos_new.html", max_history_days=current_app.config["MAX_HISTORY_DAYS"]
    )


@bp.post("")
def create_crypto():
    coingecko_id = request.form.get("coingecko_id", "").strip()
    history_days_raw = request.form.get("history_days", "").strip()
    history_days = int(history_days_raw) if history_days_raw.isdigit() else 0
    if not coingecko_id:
        flash("coingecko_id is required", "error")
        return redirect(url_for("cryptos.new_crypto"))
    if not COINGECKO_ID_RE.match(coingecko_id):
        flash("Invalid CoinGecko ID format", "error")
        return redirect(url_for("cryptos.new_crypto"))

    session = get_session()
    existing = (
        session.query(Cryptocurrency)
        .filter(Cryptocurrency.coingecko_id == coingecko_id)
        .first()
    )
    if existing:
        flash("Crypto already exists", "error")
        return redirect(url_for("cryptos.new_crypto"))

    client = CoinGeckoClient(current_app.config["COINGECKO_BASE_URL"])
    try:
        coin = client.get_coin_basic(coingecko_id)
    except CoinGeckoError as exc:
        flash(str(exc), "error")
        return redirect(url_for("cryptos.new_crypto"))

    if not coin:
        flash("CoinGecko ID not found", "error")
        return redirect(url_for("cryptos.new_crypto"))

    crypto = Cryptocurrency(
        coingecko_id=coingecko_id,
        name=coin.get("name"),
        symbol=coin.get("symbol"),
    )
    try:
        session.add(crypto)
        session.commit()
    except Exception:
        session.rollback()
        flash("Failed to save crypto", "error")
        return redirect(url_for("cryptos.new_crypto"))

    max_days = current_app.config["MAX_HISTORY_DAYS"]
    if history_days > max_days:
        history_days = max_days
        flash(f"History days limited to {max_days}", "warning")

    if history_days > 0:
        try:
            vs_currency = current_app.config["COINGECKO_VS_CURRENCY"]
            request_delay = current_app.config["COINGECKO_REQUEST_DELAY"]
            inserted = load_historical_prices(
                client, crypto, vs_currency, history_days, request_delay=request_delay
            )
            flash(f"Loaded {inserted} historical prices", "success")
        except Exception as exc:
            flash(f"Failed to load history: {exc}", "error")

    flash("Crypto added", "success")
    return redirect(url_for("dashboard.index"))
