import re
from functools import wraps

from flask import g, jsonify, redirect, request, session, url_for
from sqlalchemy import select

from .db import get_session
from .models import User, UserCrypto

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

PUBLIC_ENDPOINTS = {
    "auth.login",
    "auth.login_post",
    "auth.register",
    "auth.register_post",
    "static",
}


def load_current_user():
    user_id = session.get("user_id")
    if not user_id:
        g.user = None
        return None
    db = get_session()
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user and not user.is_active:
        user = None
    g.user = user
    return user


def require_login():
    if request.endpoint is None:
        return None
    if request.endpoint in PUBLIC_ENDPOINTS or request.endpoint.startswith("static"):
        return None
    if getattr(g, "user", None) is None:
        if request.blueprint == "api":
            return jsonify({"error": "auth required"}), 401
        next_url = request.full_path if request.query_string else request.path
        return redirect(url_for("auth.login", next=next_url))
    return None


def is_safe_next_url(next_url: str | None) -> bool:
    if not next_url:
        return False
    return next_url.startswith("/") and not next_url.startswith("//")


def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email))


def validate_password(password: str) -> list[str]:
    errors: list[str] = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters")
    if not re.search(r"[a-z]", password):
        errors.append("Password must include a lowercase letter")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must include an uppercase letter")
    if not re.search(r"\d", password):
        errors.append("Password must include a number")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("Password must include a symbol")
    return errors


def user_crypto_exists(session_db, user_id: int, crypto_id: int) -> bool:
    return (
        session_db.execute(
            select(UserCrypto.id)
            .where(UserCrypto.user_id == user_id)
            .where(UserCrypto.crypto_id == crypto_id)
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )


def require_user_crypto(session_db, user_id: int, crypto_id: int) -> UserCrypto | None:
    return session_db.execute(
        select(UserCrypto)
        .where(UserCrypto.user_id == user_id)
        .where(UserCrypto.crypto_id == crypto_id)
    ).scalar_one_or_none()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if getattr(g, "user", None) is None:
            if request.blueprint == "api":
                return jsonify({"error": "auth required"}), 401
            next_url = request.full_path if request.query_string else request.path
            return redirect(url_for("auth.login", next=next_url))
        return view(*args, **kwargs)

    return wrapped
