"""Repository helpers for ProcessedInsight."""

from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy.orm import Session

from analysis.models.domain import AnalysisResult
from ingestion.db.models import ProcessedInsight


def save_insight(
    session: Session,
    result: AnalysisResult,
    *,
    source_refs: Optional[Iterable[dict]] = None,
) -> ProcessedInsight:
    entity = ProcessedInsight(
        ticker=result.ticker,
        summary_text=result.summary_text,
        keywords=list(result.keywords),
        sentiment_score=float(result.sentiment_score),
        anomalies=[dict(a) for a in result.anomalies],
        source_refs=list(source_refs) if source_refs is not None else None,
        llm_model=result.llm_model,
        llm_tokens_prompt=int(result.llm_tokens_prompt),
        llm_tokens_completion=int(result.llm_tokens_completion),
        llm_cost=float(result.llm_cost),
    )
    session.add(entity)
    session.flush()
    return entity

