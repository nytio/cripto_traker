from flask import Blueprint, abort, current_app, render_template
from sqlalchemy import select

from ..db import get_session
from ..models import Cryptocurrency, Price
from ..services.analytics import compute_indicators

bp = Blueprint("charts", __name__)


@bp.get("/cryptos/<int:crypto_id>")
def crypto_detail(crypto_id: int):
    session = get_session()
    crypto = session.execute(
        select(Cryptocurrency).where(Cryptocurrency.id == crypto_id)
    ).scalar_one_or_none()
    if not crypto:
        abort(404)

    prices = (
        session.execute(
            select(Price)
            .where(Price.crypto_id == crypto_id)
            .order_by(Price.date.asc())
        )
        .scalars()
        .all()
    )

    rows = [
        {"date": price.date, "price": float(price.price)} for price in prices
    ]
    series = compute_indicators(rows)
    return render_template(
        "crypto_detail.html",
        crypto=crypto,
        series=series,
        currency=current_app.config["COINGECKO_VS_CURRENCY"].upper(),
    )
