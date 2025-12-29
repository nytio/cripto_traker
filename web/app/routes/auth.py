from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..auth_utils import is_safe_next_url, validate_email, validate_password
from ..db import get_session
from ..models import User

bp = Blueprint("auth", __name__)


@bp.get("/login")
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))
    next_url = request.args.get("next", "").strip()
    return render_template("auth_login.html", next_url=next_url)


@bp.post("/login")
def login_post():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    next_url = request.form.get("next", "").strip()
    if not email or not password:
        flash("Email and password are required", "error")
        return redirect(url_for("auth.login", next=next_url))

    session_db = get_session()
    user = session_db.query(User).filter(User.email == email).first()
    if not user or not user.is_active or not check_password_hash(
        user.password_hash, password
    ):
        flash("Invalid credentials", "error")
        return redirect(url_for("auth.login", next=next_url))

    session.clear()
    session["user_id"] = user.id
    if is_safe_next_url(next_url):
        return redirect(next_url)
    return redirect(url_for("dashboard.index"))


@bp.get("/register")
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))
    return render_template("auth_register.html")


@bp.post("/register")
def register_post():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    password_confirm = request.form.get("password_confirm", "")
    if not email or not password or not password_confirm:
        flash("Email and passwords are required", "error")
        return redirect(url_for("auth.register"))
    if not validate_email(email):
        flash("Email is not valid", "error")
        return redirect(url_for("auth.register"))
    if password != password_confirm:
        flash("Passwords do not match", "error")
        return redirect(url_for("auth.register"))
    errors = validate_password(password)
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("auth.register"))

    session_db = get_session()
    existing = session_db.query(User).filter(User.email == email).first()
    if existing:
        flash("Email is already registered", "error")
        return redirect(url_for("auth.register"))

    user = User(email=email, password_hash=generate_password_hash(password))
    session_db.add(user)
    session_db.commit()
    session.clear()
    session["user_id"] = user.id
    flash("Account created", "success")
    return redirect(url_for("dashboard.index"))


@bp.get("/logout")
def logout():
    return render_template("auth_logout.html")


@bp.post("/logout")
def logout_post():
    session.clear()
    flash("Logged out", "success")
    return redirect(url_for("auth.login"))
