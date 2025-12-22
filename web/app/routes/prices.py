from flask import Blueprint, current_app, flash, redirect, url_for

from ..services.coingecko import CoinGeckoClient
from ..services.price_updater import update_daily_prices

bp = Blueprint("prices", __name__, url_prefix="/prices")


@bp.post("/update")
def update_prices():
    client = CoinGeckoClient(current_app.config["COINGECKO_BASE_URL"])
    vs_currency = current_app.config["COINGECKO_VS_CURRENCY"]
    result = update_daily_prices(client, vs_currency=vs_currency)
    if result["updated"]:
        flash(f"Prices updated: {result['updated']}", "success")
    if result["errors"]:
        flash(f"Errors updating prices: {len(result['errors'])}", "error")
    return redirect(url_for("dashboard.index"))
