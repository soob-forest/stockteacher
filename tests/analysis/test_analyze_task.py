from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from llm.client.openai_client import PermanentLLMError
from analysis.tasks import analyze as analyze_mod
from ingestion.db.models import Base, RawArticle, ProcessedInsight, JobRun, JobStatus
from ingestion.db.session import get_engine


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path: Path):
    # Configure ingestion DB to a temp SQLite for both stages
    monkeypatch.setenv("POSTGRES_DSN", f"sqlite:///{tmp_path / 'analysis_task.db'}")
    monkeypatch.setenv("INGESTION_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    monkeypatch.setenv("DEFAULT_LOCALE", "ko_KR")
    yield


def _setup_articles(tmp_path: Path):
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with SessionLocal() as session:
        # Cleanup any existing rows for idempotent setup
        session.query(RawArticle).delete()
        session.commit()
        now = datetime.now(timezone.utc)
        rows = [
            RawArticle(
                ticker="AAPL",
                source="news_api",
                source_type="news",
                title="Apple beats expectations",
                body="Earnings beat market expectations.",
                url="https://example.com/a1",
                fingerprint="fp1",
                collected_at=now,
                language="en",
            ),
            RawArticle(
                ticker="AAPL",
                source="news_api",
                source_type="news",
                title="Apple guidance raised",
                body="Guidance raised for next quarter.",
                url="https://example.com/a2",
                fingerprint="fp2",
                collected_at=now,
                language="en",
            ),
        ]
        session.add_all(rows)
        session.commit()


def _provider_ok(_: Dict[str, Any]) -> Dict[str, Any]:
    resp = {
        "summary_text": "AAPL had strong earnings and raised guidance.",
        "keywords": ["apple", "earnings", "guidance"],
        "sentiment_score": 0.6,
        "anomalies": [],
    }
    return {
        "choices": [{"message": {"content": json.dumps(resp)}}],
        "usage": {"prompt_tokens": 400, "completion_tokens": 200},
        "model": "gpt-4o-mini",
    }


def _provider_costly(_: Dict[str, Any]) -> Dict[str, Any]:
    resp = {
        "summary_text": "Token usage too high.",
        "keywords": ["apple", "earnings", "guidance"],
        "sentiment_score": 0.1,
        "anomalies": [],
    }
    return {
        "choices": [{"message": {"content": json.dumps(resp)}}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 50000},
        "model": "gpt-4o-mini",
    }


def test_analyze_core_saves_insight(tmp_path: Path, monkeypatch):
    _setup_articles(tmp_path)

    analyze_mod.PROVIDER_FACTORY = lambda: _provider_ok
    saved = analyze_mod.analyze_core("AAPL")
    assert saved == 1

    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with SessionLocal() as session:
        pi = session.execute(select(ProcessedInsight).where(ProcessedInsight.ticker == "AAPL")).scalars().first()
        assert pi is not None
        assert pi.llm_model == "gpt-4o-mini"
        jr = session.execute(select(JobRun).order_by(JobRun.started_at.desc())).scalars().first()
        assert jr is not None and jr.status == JobStatus.SUCCEEDED
        assert jr.source == "openai"


def test_analyze_core_failure_marks_jobrun(tmp_path: Path):
    _setup_articles(tmp_path)

    def _provider_fail(_: Dict[str, Any]):
        raise RuntimeError("boom")

    analyze_mod.PROVIDER_FACTORY = lambda: _provider_fail

    with pytest.raises(Exception):
        analyze_mod.analyze_core("AAPL")

    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with SessionLocal() as session:
        jr = session.execute(select(JobRun).order_by(JobRun.started_at.desc())).scalars().first()
        assert jr is not None and jr.status == JobStatus.FAILED


def test_analyze_core_cost_limit_marks_jobrun(tmp_path: Path, monkeypatch):
    _setup_articles(tmp_path)
    monkeypatch.setenv("ANALYSIS_COST_LIMIT_USD", "0.001")

    analyze_mod.PROVIDER_FACTORY = lambda: _provider_costly

    with pytest.raises(PermanentLLMError):
        analyze_mod.analyze_core("AAPL")

    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with SessionLocal() as session:
        jr = session.execute(select(JobRun).order_by(JobRun.started_at.desc())).scalars().first()
        assert jr is not None
        assert jr.status == JobStatus.FAILED
        assert jr.error_message == "LLM 비용 상한 초과"
