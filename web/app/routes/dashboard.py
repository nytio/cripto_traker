from flask import Blueprint, current_app, g, render_template
from sqlalchemy import select

from ..db import get_session
from ..models import Cryptocurrency, Price, UserCrypto

bp = Blueprint("dashboard", __name__)


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
        latest_price = (
            session.execute(
                select(Price)
                .where(Price.crypto_id == crypto.id)
                .order_by(Price.date.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        rows.append({"crypto": crypto, "latest": latest_price})

    currency = current_app.config["COINGECKO_VS_CURRENCY"].upper()
    return render_template("dashboard.html", rows=rows, currency=currency)
