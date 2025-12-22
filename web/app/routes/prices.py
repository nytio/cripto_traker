from datetime import date, timedelta

from flask import Blueprint, current_app, flash, redirect, request, url_for

from ..services.coingecko import CoinGeckoClient
from ..services.price_updater import (
    backfill_historical_prices,
    update_daily_prices,
    update_single_price,
)

bp = Blueprint("prices", __name__, url_prefix="/prices")


@bp.post("/update")
def update_prices():
    client = CoinGeckoClient(
        current_app.config["COINGECKO_BASE_URL"],
        retry_count=current_app.config["COINGECKO_RETRY_COUNT"],
        retry_delay=current_app.config["COINGECKO_RETRY_DELAY"],
    )
    vs_currency = current_app.config["COINGECKO_VS_CURRENCY"]
    request_delay = current_app.config["COINGECKO_REQUEST_DELAY"]
    as_of = date.today() - timedelta(days=1)
    result = update_daily_prices(
        client, vs_currency=vs_currency, as_of=as_of, request_delay=request_delay
    )
    if result["updated"]:
        flash(f"Prices updated for {as_of}: {result['updated']}", "success")
    if result["skipped"]:
        flash(f"Prices already stored for {as_of}: {result['skipped']}", "info")
    if result["errors"]:
        flash(f"Errors updating prices: {len(result['errors'])}", "error")
    return redirect(url_for("dashboard.index"))


@bp.post("/update/<int:crypto_id>")
def update_price(crypto_id: int):
    client = CoinGeckoClient(
        current_app.config["COINGECKO_BASE_URL"],
        retry_count=current_app.config["COINGECKO_RETRY_COUNT"],
        retry_delay=current_app.config["COINGECKO_RETRY_DELAY"],
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
    days_raw = request.form.get("history_days", "").strip()
    days = int(days_raw) if days_raw.isdigit() else 0
    if days <= 0:
        flash("History days must be greater than zero", "error")
        return redirect(url_for("charts.crypto_detail", crypto_id=crypto_id))

    max_days = current_app.config["MAX_HISTORY_DAYS"]
    if days > max_days:
        days = max_days
        flash(f"History days limited to {max_days}", "warning")

    client = CoinGeckoClient(
        current_app.config["COINGECKO_BASE_URL"],
        retry_count=current_app.config["COINGECKO_RETRY_COUNT"],
        retry_delay=current_app.config["COINGECKO_RETRY_DELAY"],
    )
    vs_currency = current_app.config["COINGECKO_VS_CURRENCY"]
    request_delay = current_app.config["COINGECKO_REQUEST_DELAY"]

    try:
        result = backfill_historical_prices(
            crypto_id,
            client,
            vs_currency=vs_currency,
            days=days,
            request_delay=request_delay,
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

    return redirect(url_for("charts.crypto_detail", crypto_id=crypto_id))
