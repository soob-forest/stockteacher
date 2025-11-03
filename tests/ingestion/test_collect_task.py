from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from ingestion.db.models import Base, JobRun, JobStatus, RawArticle
from ingestion.db.session import get_engine
from ingestion.tasks import collect as collect_mod
from ingestion.connectors.news_api import NewsAPIConnector


@pytest.fixture(autouse=True)
def _set_env(monkeypatch, tmp_path: Path):
    # Configure settings to use local SQLite file
    monkeypatch.setenv("INGESTION_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("POSTGRES_DSN", f"sqlite:///{tmp_path / 'collect.db'}")
    monkeypatch.setenv("NEWS_API_KEY", "dummy")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv(
        "COLLECTION_SCHEDULES",
        json.dumps([
            {"ticker": "AAPL", "source": "news_api", "interval_minutes": 5, "enabled": True}
        ]),
    )


def _install_factory(items: List[dict[str, Any]]):
    def provider(_ticker: str, _since):
        # map test item to NewsAPI-like record shape
        return [
            {
                "title": x.get("title"),
                "description": x.get("body") or x.get("description"),
                "url": x.get("url"),
                "publishedAt": x.get("published_at"),
                "language": x.get("language"),
            }
            for x in items
        ]

    def factory(source: str):  # ignore source mapping for tests
        return NewsAPIConnector(provider=provider)

    collect_mod.CONNECTOR_FACTORY = factory


def _bootstrap_schema():
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def test_collect_core_saves_unique_records(tmp_path: Path):
    _bootstrap_schema()
    # two items where second is duplicate by url+title
    items = [
        {
            "title": "AAPL jumps",
            "body": "good earnings",
            "url": "https://ex.com/a1",
            "published_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "language": "en",
        },
        {
            "title": "AAPL jumps",
            "body": "dup",
            "url": "https://ex.com/a1",
            "published_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "language": "en",
        },
    ]
    _install_factory(items)

    saved = collect_mod.collect_core("AAPL", "news_api")
    assert saved == 1

    # Verify DB contents and JobRun status
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with SessionLocal() as session:  # type: Session
        # SQLAlchemy 2.x count
        rows = session.execute(select(RawArticle).where(RawArticle.url == "https://ex.com/a1")).scalars().all()
        assert len(rows) == 1
        jr = session.execute(select(JobRun).order_by(JobRun.started_at.desc())).scalars().first()
        assert jr is not None and jr.status == JobStatus.SUCCEEDED


def test_collect_core_failure_records_jobrun(tmp_path: Path):
    _bootstrap_schema()

    class _FailConnector:
        def fetch(self, ticker: str):
            raise RuntimeError("boom")

    collect_mod.CONNECTOR_FACTORY = lambda source: _FailConnector()

    with pytest.raises(RuntimeError):
        collect_mod.collect_core("AAPL", "news_api")

    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with SessionLocal() as session:  # type: Session
        jr = session.execute(select(JobRun).order_by(JobRun.started_at.desc())).scalars().first()
        assert jr is not None and jr.status == JobStatus.FAILED
