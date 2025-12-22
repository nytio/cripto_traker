import time

from sqlalchemy import create_engine
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
