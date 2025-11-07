"""Celery tasks for the deliver/publish stage."""

from __future__ import annotations

from celery import shared_task

from publish.materializer import materialize_reports


@shared_task(
    name="ingestion.tasks.deliver.materialize_reports",
    queue="deliver.materialize",
)
def materialize_reports_task(limit: int = 50) -> int:  # pragma: no cover - thin Celery wrapper
    """Materialize ProcessedInsight rows as report snapshots."""
    return materialize_reports(limit=limit)
