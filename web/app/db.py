import time

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

Base = declarative_base()
SessionLocal: scoped_session | None = None
Engine = None


def init_db(app) -> None:
    database_url = app.config.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    engine = create_engine(database_url, pool_pre_ping=True)
    global SessionLocal, Engine
    SessionLocal = scoped_session(
        sessionmaker(bind=engine, autocommit=False, autoflush=False)
    )
    Engine = engine

    for attempt in range(10):
        try:
            with engine.connect():
                break
        except OperationalError:
            if attempt == 9:
                raise
            time.sleep(1)

    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_forecast_model_run_columns(engine)

    @app.teardown_appcontext
    def remove_session(exception=None) -> None:
        if SessionLocal is not None:
            SessionLocal.remove()


def get_session():
    if SessionLocal is None:
        raise RuntimeError("Database not initialized")
    return SessionLocal()


def get_engine():
    if Engine is None:
        raise RuntimeError("Database not initialized")
    return Engine


def _ensure_forecast_model_run_columns(engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    for table in ("lstm_forecasts", "gru_forecasts"):
        if table not in tables:
            continue
        columns = {col["name"] for col in inspector.get_columns(table)}
        if "model_run_id" in columns:
            continue
        with engine.begin() as conn:
            conn.execute(
                text(f"ALTER TABLE {table} ADD COLUMN model_run_id INTEGER")
            )
