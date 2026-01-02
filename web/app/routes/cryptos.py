import re

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import select

from ..auth_utils import user_crypto_exists
from ..db import get_session
from ..models import Cryptocurrency, UserCrypto
from ..services.coingecko import CoinGeckoClient, CoinGeckoError
from ..services.coincap import CoincapClient
from ..services.price_updater import load_historical_prices

bp = Blueprint("cryptos", __name__, url_prefix="/cryptos")

COINGECKO_ID_RE = re.compile(r"^[a-z0-9-]{2,50}$")


@bp.get("/new")
def new_crypto():
    session = get_session()
    existing_cryptos = session.execute(
        select(Cryptocurrency).order_by(Cryptocurrency.name)
    ).scalars()
    return render_template("cryptos_new.html", existing_cryptos=existing_cryptos)


@bp.post("")
def create_crypto():
    coingecko_id = request.form.get("coingecko_id", "").strip()
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
        if user_crypto_exists(session, g.user.id, existing.id):
            flash("Crypto already in your dashboard", "info")
            return redirect(url_for("dashboard.index"))
        try:
            session.add(UserCrypto(user_id=g.user.id, crypto_id=existing.id))
            session.commit()
        except Exception:
            session.rollback()
            flash("Failed to add crypto to dashboard", "error")
            return redirect(url_for("cryptos.new_crypto"))
        flash("Crypto added to dashboard", "success")
        return redirect(url_for("dashboard.index"))

    client = CoinGeckoClient(
        current_app.config["COINGECKO_BASE_URL"],
        retry_count=current_app.config["COINGECKO_RETRY_COUNT"],
        retry_delay=current_app.config["COINGECKO_RETRY_DELAY"],
        api_key=current_app.config["COINGECKO_API_KEY"],
        api_key_header=current_app.config["COINGECKO_API_KEY_HEADER"],
    )
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
        session.flush()
        session.add(UserCrypto(user_id=g.user.id, crypto_id=crypto.id))
        session.commit()
    except Exception:
        session.rollback()
        flash("Failed to save crypto", "error")
        return redirect(url_for("cryptos.new_crypto"))

    max_days = current_app.config["MAX_HISTORY_DAYS"]
    backfill_max_days = min(365, max_days)
    history_days = backfill_max_days
    try:
        vs_currency = current_app.config["COINGECKO_VS_CURRENCY"]
        request_delay = current_app.config["COINGECKO_REQUEST_DELAY"]
        coincap_base_url = current_app.config["COINCAP_BASE_URL"]
        coincap_client = None
        if coincap_base_url:
            coincap_client = CoincapClient(
                coincap_base_url,
                retry_count=current_app.config["COINCAP_RETRY_COUNT"],
                retry_delay=current_app.config["COINCAP_RETRY_DELAY"],
                api_key=current_app.config["COINCAP_API_KEY"],
            )
        coincap_request_delay = current_app.config["COINCAP_REQUEST_DELAY"]
        inserted = load_historical_prices(
            client,
            crypto,
            vs_currency,
            history_days,
            request_delay=request_delay,
            max_history_days=max_days,
            max_request_days=backfill_max_days,
            coincap_client=coincap_client,
            coincap_request_delay=coincap_request_delay,
        )
        flash(f"Loaded {inserted} historical prices", "success")
    except Exception as exc:
        flash(f"Failed to load history: {exc}", "error")

    flash("Crypto added", "success")
    return redirect(url_for("dashboard.index"))


@bp.post("/<int:crypto_id>/remove")
def remove_crypto(crypto_id: int):
    session = get_session()
    association = (
        session.query(UserCrypto)
        .filter(UserCrypto.user_id == g.user.id, UserCrypto.crypto_id == crypto_id)
        .first()
    )
    if not association:
        flash("Crypto not in your dashboard", "error")
        return redirect(url_for("dashboard.index"))
    session.delete(association)
    session.commit()
    flash("Crypto removed from dashboard", "success")
    return redirect(url_for("dashboard.index"))
