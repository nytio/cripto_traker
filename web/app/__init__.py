from flask import Flask

from .config import Config
from .db import init_db
from .routes import api, charts, cryptos, dashboard, prices


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config())

    init_db(app)

    app.register_blueprint(dashboard.bp)
    app.register_blueprint(cryptos.bp)
    app.register_blueprint(prices.bp)
    app.register_blueprint(charts.bp)
    app.register_blueprint(api.bp)

    return app
