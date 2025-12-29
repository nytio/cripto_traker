from datetime import date, timedelta

from flask import Blueprint, current_app, flash, g, redirect, request, url_for
from sqlalchemy import select

from ..auth_utils import require_user_crypto
from ..services.coingecko import CoinGeckoClient
from ..services.coincap import CoincapClient
from ..services.price_updater import (
    backfill_historical_prices,
    update_daily_prices,
    update_single_price,
)
from ..db import get_session
from ..models import UserCrypto

bp = Blueprint("prices", __name__, url_prefix="/prices")


def _redirect_with_days(crypto_id: int):
    days_raw = request.form.get("range_days", "").strip()
    if days_raw.isdigit():
        return redirect(
            url_for("charts.crypto_detail", crypto_id=crypto_id, days=days_raw)
        )
    return redirect(url_for("charts.crypto_detail", crypto_id=crypto_id))


@bp.post("/update")
def update_prices():
    session = get_session()
    crypto_ids = (
        session.execute(
            select(UserCrypto.crypto_id).where(UserCrypto.user_id == g.user.id)
        )
        .scalars()
        .all()
    )
    if not crypto_ids:
        flash("No cryptos in your dashboard to update", "info")
        return redirect(url_for("dashboard.index"))
    client = CoinGeckoClient(
        current_app.config["COINGECKO_BASE_URL"],
        retry_count=current_app.config["COINGECKO_RETRY_COUNT"],
        retry_delay=current_app.config["COINGECKO_RETRY_DELAY"],
        api_key=current_app.config["COINGECKO_API_KEY"],
        api_key_header=current_app.config["COINGECKO_API_KEY_HEADER"],
    )
    vs_currency = current_app.config["COINGECKO_VS_CURRENCY"]
    request_delay = current_app.config["COINGECKO_REQUEST_DELAY"]
    as_of = date.today() - timedelta(days=1)
    result = update_daily_prices(
        client,
        vs_currency=vs_currency,
        as_of=as_of,
        request_delay=request_delay,
        crypto_ids=crypto_ids,
    )
    if result["updated"]:
        flash(
            (
                f"Prices updated through {as_of}: "
                f"{result['inserted']} prices across {result['updated']} cryptos"
            ),
            "success",
        )
    if result["skipped"]:
        flash(f"No new prices needed through {as_of}: {result['skipped']}", "info")
    if result["errors"]:
        flash(f"Errors updating prices: {len(result['errors'])}", "error")
    return redirect(url_for("dashboard.index"))


@bp.post("/update/<int:crypto_id>")
def update_price(crypto_id: int):
    session = get_session()
    if not require_user_crypto(session, g.user.id, crypto_id):
        flash("Crypto not in your dashboard", "error")
        return redirect(url_for("dashboard.index"))
    client = CoinGeckoClient(
        current_app.config["COINGECKO_BASE_URL"],
        retry_count=current_app.config["COINGECKO_RETRY_COUNT"],
        retry_delay=current_app.config["COINGECKO_RETRY_DELAY"],
        api_key=current_app.config["COINGECKO_API_KEY"],
        api_key_header=current_app.config["COINGECKO_API_KEY_HEADER"],
    )
    vs_currency = current_app.config["COINGECKO_VS_CURRENCY"]
    as_of = date.today() - timedelta(days=1)
    try:
        updated = update_single_price(
            crypto_id, client, vs_currency=vs_currency, as_of=as_of
        )
        if updated:
            flash(f"Price updated for {as_of}", "success")
        else:
            flash(f"Price already stored for {as_of}", "info")
    except Exception as exc:
        flash(f"Failed to update price: {exc}", "error")
    return redirect(url_for("dashboard.index"))


@bp.post("/backfill/<int:crypto_id>")
def backfill_prices(crypto_id: int):
    session = get_session()
    if not require_user_crypto(session, g.user.id, crypto_id):
        flash("Crypto not in your dashboard", "error")
        return redirect(url_for("dashboard.index"))
    days_raw = request.form.get("history_days", "").strip()
    days = int(days_raw) if days_raw.isdigit() else 0
    if days <= 0:
        flash("History days must be greater than zero", "error")
        return _redirect_with_days(crypto_id)

    max_days = current_app.config["MAX_HISTORY_DAYS"]
    max_request_days = min(365, max_days)
    if days > max_days:
        days = max_days
        flash(f"History days limited to {max_days}", "warning")

    client = CoinGeckoClient(
        current_app.config["COINGECKO_BASE_URL"],
        retry_count=current_app.config["COINGECKO_RETRY_COUNT"],
        retry_delay=current_app.config["COINGECKO_RETRY_DELAY"],
        api_key=current_app.config["COINGECKO_API_KEY"],
        api_key_header=current_app.config["COINGECKO_API_KEY_HEADER"],
    )
    coincap_base_url = current_app.config["COINCAP_BASE_URL"]
    coincap_client = None
    if coincap_base_url:
        coincap_client = CoincapClient(
            coincap_base_url,
            retry_count=current_app.config["COINCAP_RETRY_COUNT"],
            retry_delay=current_app.config["COINCAP_RETRY_DELAY"],
            api_key=current_app.config["COINCAP_API_KEY"],
        )
    vs_currency = current_app.config["COINGECKO_VS_CURRENCY"]
    request_delay = current_app.config["COINGECKO_REQUEST_DELAY"]
    coincap_request_delay = current_app.config["COINCAP_REQUEST_DELAY"]

    try:
        result = backfill_historical_prices(
            crypto_id,
            client,
            vs_currency=vs_currency,
            days=days,
            request_delay=request_delay,
            max_history_days=max_days,
            max_request_days=max_request_days,
            coincap_client=coincap_client,
            coincap_request_delay=coincap_request_delay,
        )
        if result["requested"] == 0:
            flash("History already complete for this range", "success")
        else:
            flash(
                f"Backfill done: {result['inserted']} prices from {result['requested']} request(s)",
                "success",
            )
    except Exception as exc:
        flash(f"Failed to backfill history: {exc}", "error")

    return _redirect_with_days(crypto_id)
