from flask import Blueprint, flash, redirect, render_template, request, url_for

bp = Blueprint("cryptos", __name__, url_prefix="/cryptos")


@bp.get("/new")
def new_crypto():
    return render_template("cryptos_new.html")


@bp.post("")
def create_crypto():
    coingecko_id = request.form.get("coingecko_id", "").strip()
    if not coingecko_id:
        flash("coingecko_id is required", "error")
        return redirect(url_for("cryptos.new_crypto"))

    flash("Crypto saved (placeholder)", "success")
    return redirect(url_for("dashboard.index"))
