import re

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from ..db import get_session
from ..models import Cryptocurrency
from ..services.coingecko import CoinGeckoClient, CoinGeckoError

bp = Blueprint("cryptos", __name__, url_prefix="/cryptos")

COINGECKO_ID_RE = re.compile(r"^[a-z0-9-]{2,50}$")


@bp.get("/new")
def new_crypto():
    return render_template("cryptos_new.html")


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

    flash("Crypto added", "success")
    return redirect(url_for("dashboard.index"))
