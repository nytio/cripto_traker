from flask import Blueprint, render_template

bp = Blueprint("charts", __name__)


@bp.get("/cryptos/<int:crypto_id>")
def crypto_detail(crypto_id: int):
    return render_template("crypto_detail.html", crypto_id=crypto_id)
