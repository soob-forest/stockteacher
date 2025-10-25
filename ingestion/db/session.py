"""Session helpers for the ingestion database."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ingestion.settings import Settings, get_settings

_ENGINE: Engine | None = None
_SESSIONMAKER: sessionmaker[Session] | None = None
_CURRENT_DSN: str | None = None


def get_engine(settings: Settings | None = None) -> Engine:
    """Return a memoized SQLAlchemy engine."""
    global _ENGINE, _SESSIONMAKER, _CURRENT_DSN

    config = settings or get_settings()
    if _ENGINE is None or _CURRENT_DSN != config.postgres_dsn:
        _ENGINE = create_engine(config.postgres_dsn, future=True)
        _SESSIONMAKER = sessionmaker(
            bind=_ENGINE,
            expire_on_commit=False,
            autoflush=False,
            future=True,
        )
        _CURRENT_DSN = config.postgres_dsn
    return _ENGINE


def get_sessionmaker(settings: Settings | None = None) -> sessionmaker[Session]:
    """Return a memoized sessionmaker."""
    engine = get_engine(settings)
    assert _SESSIONMAKER is not None  # for mypy
    return _SESSIONMAKER


@contextmanager
def session_scope(settings: Settings | None = None) -> Iterator[Session]:
    """Provide a transactional scope for DB operations."""
    session = get_sessionmaker(settings)()
    try:
        yield session
        session.commit()
    except Exception:  # pragma: no cover - re-raise after rollback
        session.rollback()
        raise
    finally:
        session.close()
