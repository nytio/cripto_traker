from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

Base = declarative_base()
SessionLocal: scoped_session | None = None


def init_db(app) -> None:
    database_url = app.config.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    engine = create_engine(database_url, pool_pre_ping=True)
    global SessionLocal
    SessionLocal = scoped_session(
        sessionmaker(bind=engine, autocommit=False, autoflush=False)
    )

    @app.teardown_appcontext
    def remove_session(exception=None) -> None:
        if SessionLocal is not None:
            SessionLocal.remove()


def get_session():
    if SessionLocal is None:
        raise RuntimeError("Database not initialized")
    return SessionLocal()
