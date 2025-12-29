from flask import Flask, g
from flask_wtf.csrf import CSRFProtect

from .auth_utils import load_current_user, require_login
from .config import Config
from .db import init_db
from .routes import api, auth, charts, cryptos, dashboard, prices

csrf = CSRFProtect()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config())

    csrf.init_app(app)
    init_db(app)

    @app.before_request
    def load_user():
        load_current_user()

    @app.before_request
    def enforce_login():
        return require_login()

    @app.context_processor
    def inject_user():
        return {"current_user": getattr(g, "user", None)}

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src-elem 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src-attr 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'",
        )
        return response

    app.register_blueprint(dashboard.bp)
    app.register_blueprint(cryptos.bp)
    app.register_blueprint(prices.bp)
    app.register_blueprint(charts.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(auth.bp)

    return app
