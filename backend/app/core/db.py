"""Engine e sessione SQLAlchemy 2.x sul database SQLite condiviso."""

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    """Base dichiarativa per tutti i model."""


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _conn_record):
    """WAL + busy_timeout: scritture concorrenti sicure con più utenti in parallelo."""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """Dependency FastAPI: fornisce una sessione e la chiude a fine richiesta."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
