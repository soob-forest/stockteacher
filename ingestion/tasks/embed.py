"""Celery task to generate embeddings for report snapshots and upsert into Chroma."""

from __future__ import annotations

import uuid
from typing import List

from celery import shared_task
from sqlalchemy import select

from api.database import get_session as get_api_session
from api.db_models import ReportSnapshot
from ingestion.services.chroma_client import ChromaClient, default_chroma_client
from llm.embeddings import EmbeddingError, EmbeddingSettings, embed_texts
from ingestion.utils.logging import get_logger


def _build_text(snapshot: ReportSnapshot) -> str:
    parts: List[str] = []
    if snapshot.headline:
        parts.append(snapshot.headline)
    if snapshot.summary_text:
        parts.append(snapshot.summary_text)
    keywords = snapshot.keywords or []
    if keywords:
        parts.append("Keywords: " + ", ".join(keywords))
    return "\n".join(parts)


def _snapshot_metadata(snapshot: ReportSnapshot) -> dict:
    summary = (snapshot.summary_text or "")[:1000]
    return {
        "ticker": snapshot.ticker,
        "published_at": snapshot.published_at.isoformat() if snapshot.published_at else None,
        "keywords": snapshot.keywords or [],
        "anomaly_score": snapshot.anomaly_score,
        "headline": snapshot.headline,
        "summary_text": summary,
    }


def embed_reports_core(limit: int = 50) -> int:
    """ReportSnapshot을 임베딩해 Chroma에 업서트한다."""
    logger = get_logger(__name__)
    trace_id = uuid.uuid4().hex
    client: ChromaClient = default_chroma_client()
    settings = EmbeddingSettings.from_env()

    with get_api_session() as session:
        rows = session.scalars(
            select(ReportSnapshot)
            .where(ReportSnapshot.status != "hidden")
            .order_by(ReportSnapshot.published_at.desc())
            .limit(limit)
        ).all()
        if not rows:
            return 0

        texts = [_build_text(row) for row in rows]
        total_chars = sum(len(t) for t in texts)
        est_tokens = max(1, total_chars // 4)
        try:
            embeddings = embed_texts(texts, settings=settings)
        except EmbeddingError as exc:
            logger.error("embed.failed", extra={"trace_id": trace_id, "error": str(exc)})
            raise

        client.heartbeat()
        client.ensure_collection()
        client.upsert(
            ids=[row.insight_id for row in rows],
            embeddings=embeddings,
            metadatas=[_snapshot_metadata(row) for row in rows],
        )

        hidden_ids = [
            snap.insight_id
            for snap in session.scalars(
                select(ReportSnapshot.insight_id).where(ReportSnapshot.status == "hidden")
            )
        ]
        if hidden_ids:
            client.delete(ids=hidden_ids)
            logger.info(
                "embed.deleted_hidden",
                extra={"trace_id": trace_id, "count": len(hidden_ids)},
            )

        logger.info(
            "embed.upserted",
            extra={
                "trace_id": trace_id,
                "count": len(rows),
                "collection": client.collection,
                "estimated_tokens": est_tokens,
                "total_chars": total_chars,
            },
        )
        return len(rows)


@shared_task(
    name="ingestion.tasks.embed.embed_reports",
    queue="analysis.embed",
)
def embed_reports(limit: int = 50) -> int:  # pragma: no cover - thin Celery wrapper
    return embed_reports_core(limit)
