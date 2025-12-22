from flask import Blueprint, jsonify
from sqlalchemy import select

from ..db import get_session
from ..models import Price

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/cryptos/<int:crypto_id>/prices")
def prices(crypto_id: int):
    session = get_session()
    prices = (
        session.execute(
            select(Price)
            .where(Price.crypto_id == crypto_id)
            .order_by(Price.date.asc())
        )
        .scalars()
        .all()
    )
    payload = [
        {"date": price.date.isoformat(), "price": float(price.price)}
        for price in prices
    ]
    return jsonify(payload)
