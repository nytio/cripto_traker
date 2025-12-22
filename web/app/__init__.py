from flask import Flask
from flask_wtf.csrf import CSRFProtect

from .config import Config
from .db import init_db
from .routes import api, charts, cryptos, dashboard, prices

csrf = CSRFProtect()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config())

    csrf.init_app(app)
    init_db(app)

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

    return app
