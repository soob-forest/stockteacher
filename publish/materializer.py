from __future__ import annotations

import logging
import uuid
from typing import Iterable, Sequence

from sqlalchemy import select

from api.database import get_session
from api.db_models import ReportSnapshot
from ingestion.db.models import JobStage, ProcessedInsight
from ingestion.db.session import session_scope
from ingestion.repositories.articles import JobRunRecorder
from publish.notifier import dispatch_urgent_notifications, is_urgent_snapshot

logger = logging.getLogger(__name__)


def materialize_reports(*, limit: int = 50, ticker: str | None = None) -> int:
    """Persist ProcessedInsight rows as web-facing report snapshots.

    Returns the number of new snapshots created.
    """
    inserted = 0
    with session_scope() as ingestion_session:
        stmt = (
            select(ProcessedInsight)
            .order_by(ProcessedInsight.generated_at.desc())
        )
        if ticker:
            stmt = stmt.where(ProcessedInsight.ticker == ticker.upper())
        if limit:
            stmt = stmt.limit(limit)

        insights: Sequence[ProcessedInsight] = list(
            ingestion_session.execute(stmt).scalars().unique().all()
        )
        if not insights:
            return 0

        with get_session() as api_session:
            existing_ids = {
                row
                for row in api_session.execute(
                    select(ReportSnapshot.insight_id)
                ).scalars()
            }

            for insight in insights:
                insight_id = str(insight.id)
                if insight_id in existing_ids:
                    continue

                trace_id = str(uuid.uuid4())
                with JobRunRecorder(
                    ingestion_session,
                    stage=JobStage.DELIVER,
                    ticker=insight.ticker,
                    source="web_portal",
                    task_name="publish.materialize_reports",
                    trace_id=trace_id,
                ):
                    snapshot = ReportSnapshot(
                        insight_id=insight_id,
                        ticker=insight.ticker,
                        headline=_derive_headline(insight.summary_text),
                        summary_text=insight.summary_text,
                        published_at=insight.generated_at,
                        status=_infer_status(insight),
                        sentiment_score=float(insight.sentiment_score),
                        anomaly_score=_compute_anomaly_score(
                            insight.anomalies or []
                        ),
                        tags=_derive_tags(
                            insight.keywords or [], insight.anomalies or []
                        ),
                        keywords=list(insight.keywords or []),
                        source_refs=list(insight.source_refs or []),
                        attachments=[],
                    )
                    api_session.add(snapshot)
                    api_session.flush()

                    try:
                        dispatched = dispatch_urgent_notifications(
                            api_session, snapshot
                        )
                        urgent, reason = is_urgent_snapshot(snapshot)
                        if urgent and dispatched:
                            logger.info(
                                "publish.urgent_dispatched",
                                extra={
                                    "trace_id": trace_id,
                                    "insight_id": insight_id,
                                    "ticker": insight.ticker,
                                    "recipients": len(dispatched),
                                    "reason": reason,
                                },
                            )
                    except Exception:
                        logger.exception(
                            "publish.urgent_dispatch_failed",
                            extra={"trace_id": trace_id, "insight_id": insight_id},
                        )

                existing_ids.add(insight_id)
                inserted += 1
                logger.info(
                    "publish.materialized",
                    extra={
                        "trace_id": trace_id,
                        "insight_id": insight_id,
                        "ticker": insight.ticker,
                    },
                )
    return inserted


def _derive_headline(summary: str) -> str:
    cleaned_lines = [line.strip() for line in summary.splitlines() if line.strip()]
    if not cleaned_lines:
        return "요약이 제공되지 않았습니다."
    candidate = cleaned_lines[0]
    for delimiter in (".", "!", "?"):
        if delimiter in candidate:
            head = candidate.split(delimiter)[0].strip()
            if head:
                candidate = f"{head}{delimiter}"
                break
    return _truncate(candidate, 120)


def _truncate(value: str, length: int) -> str:
    if len(value) <= length:
        return value
    return value[: length - 1].rstrip() + "…"


def _compute_anomaly_score(anomalies: Iterable[dict]) -> float:
    scores: list[float] = []
    for anomaly in anomalies:
        for key in ("score", "severity", "value"):
            raw = anomaly.get(key)
            if isinstance(raw, (int, float)):
                scores.append(float(raw))
                break
    return max(scores) if scores else 0.0


def _derive_tags(keywords: Iterable[str], anomalies: Iterable[dict]) -> list[str]:
    tags: list[str] = []
    for keyword in keywords:
        if keyword and keyword not in tags:
            tags.append(str(keyword))
        if len(tags) >= 5:
            return tags
    for anomaly in anomalies:
        label = anomaly.get("label") or anomaly.get("type")
        if label and label not in tags:
            tags.append(str(label))
        if len(tags) >= 5:
            break
    return tags


def _infer_status(insight: ProcessedInsight) -> str:
    if abs(float(insight.sentiment_score)) >= 0.9:
        return "draft"
    if not (insight.keywords or []):
        return "draft"
    if not (insight.anomalies or []) and len(insight.summary_text or "") < 100:
        return "draft"
    return "published"
