from __future__ import annotations

import importlib
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import delete, select


def _prepare_environments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ingestion_url = f"sqlite:///{tmp_path}/ingestion.db"
    portal_url = f"sqlite:///{tmp_path}/portal.db"
    monkeypatch.setenv("POSTGRES_DSN", ingestion_url)
    monkeypatch.setenv("DATABASE_URL", portal_url)

    from ingestion.settings import reset_settings_cache

    reset_settings_cache()

    ingestion_session_module = importlib.import_module("ingestion.db.session")
    api_database_module = importlib.import_module("api.database")

    ingestion_session = importlib.reload(ingestion_session_module)
    api_database = importlib.reload(api_database_module)

    api_database.init_db()

    from ingestion.db.models import Base as IngestionBase

    IngestionBase.metadata.create_all(bind=ingestion_session.get_engine())

    from api.db_models import Base as ApiBase, ReportSnapshot

    ApiBase.metadata.create_all(bind=api_database.engine)
    with api_database.get_session() as api_session:
        api_session.execute(delete(ReportSnapshot))

    return ingestion_session, api_database


def test_materialize_reports_creates_snapshots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ingestion_session, api_database = _prepare_environments(tmp_path, monkeypatch)

    from ingestion.db.models import JobRun, JobStage, JobStatus, ProcessedInsight

    # Clean slate
    with ingestion_session.session_scope() as session:
        session.execute(delete(ProcessedInsight))

    generated_at = datetime(2025, 5, 1, 12, 0, tzinfo=timezone.utc)

    with ingestion_session.session_scope() as session:
        insight = ProcessedInsight(
            ticker="AAPL",
            summary_text="Apple posts record revenue growth. Guidance lifted for the next quarter.",
            keywords=["revenue", "guidance", "growth"],
            sentiment_score=0.62,
            anomalies=[{"label": "guidance", "score": 0.44}],
            source_refs=[{"title": "Earnings call", "url": "https://example.com/aapl"}],
            generated_at=generated_at,
            llm_model="gpt-4o-mini",
            llm_tokens_prompt=1200,
            llm_tokens_completion=320,
            llm_cost=0.18,
        )
        session.add(insight)
        session.flush()
        insight_id = str(insight.id)

    materializer = importlib.import_module("publish.materializer")
    materializer = importlib.reload(materializer)

    inserted = materializer.materialize_reports(limit=10)
    assert inserted == 1

    from api.db_models import ReportSnapshot

    with api_database.get_session() as api_session:
        rows = list(api_session.execute(select(ReportSnapshot)).scalars())
        assert len(rows) == 1
        snapshot = rows[0]
        assert snapshot.insight_id == insight_id
        assert snapshot.ticker == "AAPL"
        assert snapshot.summary_text.startswith("Apple posts record revenue")
        assert snapshot.sentiment_score == pytest.approx(0.62)
        assert snapshot.anomaly_score == pytest.approx(0.44)
        assert "guidance" in snapshot.tags
        published = snapshot.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        assert published == generated_at

    with ingestion_session.session_scope() as session:
        job_runs = list(
            session.execute(
                select(JobRun).where(JobRun.stage == JobStage.DELIVER)
            ).scalars()
        )
        assert len(job_runs) == 1
        assert job_runs[0].status == JobStatus.SUCCEEDED

    # Second run should be idempotent
    inserted_again = materializer.materialize_reports(limit=10)
    assert inserted_again == 0
