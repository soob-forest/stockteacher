from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from analysis.models.domain import AnalysisResult, AnomalyItem
from analysis.repositories.insights import save_insight
from ingestion.db.models import Base, ProcessedInsight


def test_save_insight_roundtrip(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'analysis.db'}"
    engine = create_engine(url, future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    res = AnalysisResult(
        ticker="AAPL",
        summary_text="Strong results",
        keywords=["apple", "growth"],
        sentiment_score=0.5,
        anomalies=[AnomalyItem(label="surge", description="Volume spike", score=0.7)],
        llm_model="gpt-4o-mini",
        llm_tokens_prompt=100,
        llm_tokens_completion=50,
        llm_cost=0.001,
    )

    with SessionLocal() as session:
        entity = save_insight(session, res, source_refs=None)
        session.commit()

    with SessionLocal() as session:
        fetched = session.execute(select(ProcessedInsight).where(ProcessedInsight.id == entity.id)).scalars().first()
        assert fetched is not None
        assert fetched.ticker == "AAPL"
        assert fetched.llm_model == "gpt-4o-mini"
        assert fetched.sentiment_score == 0.5

