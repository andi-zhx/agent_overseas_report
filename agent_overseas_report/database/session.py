"""Database engine/session helpers for SQLAlchemy 2.0."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from agent_overseas_report.database.models import Base

DEFAULT_SQLITE_PATH = Path(".data/overseas_report.sqlite3")


def get_database_url() -> str:
    """Return configured database URL, defaulting to a local SQLite file."""

    return os.getenv("OVERSEAS_REPORT_DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")


def create_database_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine with SQLite-friendly defaults."""

    url = database_url or get_database_url()
    if url.startswith("sqlite:///"):
        db_path = url.replace("sqlite:///", "", 1)
        if db_path and db_path != ":memory:":
            Path(db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build a SQLAlchemy 2.0 session factory."""

    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def initialize_database(engine: Engine) -> None:
    """Create all application tables if they do not already exist."""

    Base.metadata.create_all(engine)


def session_scope(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Provide a transaction boundary around repository operations."""

    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
