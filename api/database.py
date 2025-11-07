from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from . import db_models

DEFAULT_SQLITE_PATH = Path("./var/storage/app.db")


def _make_engine() -> Engine:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        DEFAULT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite:///{DEFAULT_SQLITE_PATH}"
        connect_args = {"check_same_thread": False}
    else:
        connect_args = {}
    engine = create_engine(
        database_url,
        future=True,
        echo=False,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    return engine


engine = _make_engine()
SessionLocal = sessionmaker(
    bind=engine, autocommit=False, autoflush=False, future=True
)


def init_db() -> None:
    db_models.Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        db_models.seed_reports(session)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def session_dependency() -> Generator[Session, None, None]:
    with get_session() as session:
        yield session
