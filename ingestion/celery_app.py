"""Celery 애플리케이션 부트스트랩."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict

from celery import Celery
from celery.schedules import schedule as celery_schedule

from .settings import CollectionSchedule, Settings, get_settings
from .utils.logging import configure_logging

_CELERY_APP: Celery | None = None


def create_celery_app(settings: Settings | None = None) -> Celery:
    """설정을 기반으로 Celery 인스턴스를 생성한다."""
    config = settings or get_settings()
    configure_logging(config.structlog_level, json_enabled=config.log_json)

    app = Celery("ingestion", broker=config.redis_url, backend=config.redis_url)
    app.conf.update(
        task_default_queue="ingestion.default",
        task_default_exchange="ingestion",
        task_default_routing_key="ingestion.default",
        task_soft_time_limit=config.celery_task_soft_time_limit,
        worker_concurrency=config.celery_worker_concurrency,
        beat_schedule=_build_beat_schedule(config),
        timezone="UTC",
        enable_utc=True,
        worker_send_task_events=True,
        task_send_sent_event=True,
    )

    app.autodiscover_tasks(["ingestion.tasks"])
    _install_signal_handlers(app)
    return app


def get_celery_app() -> Celery:
    """싱글톤 Celery 인스턴스를 반환한다."""
    global _CELERY_APP
    if _CELERY_APP is None:
        _CELERY_APP = create_celery_app()
    return _CELERY_APP


def _build_beat_schedule(settings: Settings) -> Dict[str, Dict[str, Any]]:
    schedule: Dict[str, Dict[str, Any]] = {}
    for index, item in enumerate(settings.collection_schedules):
        if not item.enabled:
            continue
        schedule_name = _build_schedule_name(item, index)
        run_every = celery_schedule(timedelta(minutes=item.interval_minutes))
        schedule[schedule_name] = {
            "task": "ingestion.tasks.collect.collect_articles_for_ticker",
            "schedule": run_every,
            "args": (item.ticker, item.source),
            "options": {"queue": "ingestion.collect"},
        }
    return schedule


def _build_schedule_name(item: CollectionSchedule, index: int) -> str:
    return f"collect.{item.source}.{item.ticker.lower()}.{index}"


def _configure_logging(level_name: str) -> None:  # backward-compat shim
    # Kept for compatibility; delegate to new utility without JSON.
    configure_logging(level_name, json_enabled=False)


def _install_signal_handlers(app: Celery) -> None:
    try:
        from celery import signals
    except ImportError:
        logging.getLogger(__name__).warning("Celery signals를 가져오지 못해 종료 훅을 설정하지 못했습니다.")
        return

    logger = logging.getLogger("ingestion.worker")

    @signals.worker_shutdown.connect  # type: ignore[attr-defined]
    def _on_worker_shutdown(sender=None, **kwargs):  # noqa: ANN001
        logger.info("Celery worker shutdown detected", extra={"sender": sender})
