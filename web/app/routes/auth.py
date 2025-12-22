from flask import Blueprint, render_template

bp = Blueprint("auth", __name__)


@bp.get("/login")
def login():
    return render_template("auth_login.html")


@bp.get("/logout")
def logout():
    return render_template("auth_logout.html")
