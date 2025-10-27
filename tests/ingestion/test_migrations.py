from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from ingestion.db.models import JobRun, JobStage, JobStatus, RawArticle


@pytest.fixture()
def sqlite_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'ingestion.db'}"


def _upgrade_database(db_url: str) -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "ingestion/db/migrations")
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")


def test_migrations_create_expected_tables(sqlite_url: str) -> None:
    _upgrade_database(sqlite_url)
    engine = create_engine(sqlite_url, future=True)
    inspector = inspect(engine)

    tables = set(inspector.get_table_names())
    assert {"raw_articles", "job_runs", "processed_insights"}.issubset(tables)

    raw_columns = {column["name"] for column in inspector.get_columns("raw_articles")}
    assert {"ticker", "fingerprint", "collected_at"}.issubset(raw_columns)

    job_columns = {column["name"] for column in inspector.get_columns("job_runs")}
    assert {"stage", "status", "retry_count"}.issubset(job_columns)

    pi_columns = {column["name"] for column in inspector.get_columns("processed_insights")}
    assert {"ticker", "summary_text", "llm_model", "llm_cost"}.issubset(pi_columns)


def test_models_roundtrip(sqlite_url: str) -> None:
    _upgrade_database(sqlite_url)
    engine = create_engine(sqlite_url, future=True)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    with SessionLocal() as session:  # type: Session
        article = RawArticle(
            ticker="AAPL",
            source="news_api",
            source_type="news",
            title="Apple hits new high",
            body="Some body",
            url="https://example.com/article",
            fingerprint="abc123",
            collected_at=datetime.now(timezone.utc),
            language="ko",
        )
        job = JobRun(stage=JobStage.COLLECT, status=JobStatus.RUNNING, task_name="collect_articles")
        # Insert minimal processed insight row as well
        from ingestion.db.models import ProcessedInsight

        pi = ProcessedInsight(
            ticker="AAPL",
            summary_text="Summary",
            keywords=["apple", "earnings"],
            sentiment_score=0.1,
            anomalies=[],
            source_refs=None,
            llm_model="gpt-4o-mini",
            llm_tokens_prompt=10,
            llm_tokens_completion=5,
            llm_cost=0.0001,
        )

        session.add_all([article, job, pi])
        session.commit()
        session.refresh(article)
        session.refresh(job)
        session.refresh(pi)
        session.expunge(article)
        session.expunge(job)
        session.expunge(pi)

    assert article.id is not None
    assert article.created_at is not None
    assert job.retry_count == 0
    assert job.status == JobStatus.RUNNING
    assert job.updated_at is not None
    assert job.created_at <= job.updated_at
