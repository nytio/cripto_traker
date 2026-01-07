from flask import Blueprint, current_app, g, render_template
from sqlalchemy import select

from ..db import get_session
from ..models import Cryptocurrency, Price, ProphetForecast, UserCrypto
from ..services.analytics import compute_indicators

bp = Blueprint("dashboard", __name__)


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
