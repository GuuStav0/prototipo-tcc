from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator

from .config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime) -> datetime:
    """Datas sem fuso são tratadas como UTC; com fuso, convertidas para UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class UTCDateTime(TypeDecorator):
    """O SQLite não guarda fuso: grava em UTC sem fuso e devolve com fuso UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return as_utc(value).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(conn, _):
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    return engine


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
