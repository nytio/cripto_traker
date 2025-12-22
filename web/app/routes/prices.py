from flask import Blueprint, current_app, flash, redirect, url_for

from ..services.coingecko import CoinGeckoClient
from ..services.price_updater import update_daily_prices

bp = Blueprint("prices", __name__, url_prefix="/prices")


@bp.post("/update")
def update_prices():
    client = CoinGeckoClient(current_app.config["COINGECKO_BASE_URL"])
    result = update_daily_prices(client)
    flash(f"Prices updated: {result['updated']}", "success")
    return redirect(url_for("dashboard.index"))
