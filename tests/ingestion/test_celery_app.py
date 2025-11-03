import pytest

celery = pytest.importorskip("celery")  # noqa: F841

from ingestion.celery_app import create_celery_app
from ingestion.settings import CollectionSchedule, Settings


def _make_settings() -> Settings:
    return Settings(
        redis_url="redis://localhost:6379/0",
        news_api_key="secret",
        postgres_dsn="postgresql://user:pass@localhost:5432/app",
        local_storage_root="./var/storage",
        collection_schedules=[
            CollectionSchedule(ticker="AAPL", source="news_api", interval_minutes=5, enabled=True),
            CollectionSchedule(ticker="TSLA", source="news_api", interval_minutes=10, enabled=False),
        ],
        structlog_level="DEBUG",
        celery_worker_concurrency=2,
    )


def test_create_celery_app_builds_enabled_schedule():
    settings = _make_settings()

    app = create_celery_app(settings)

    assert isinstance(app.conf.beat_schedule, dict)
    assert any("aapl" in key for key in app.conf.beat_schedule.keys())
    assert all("tsla" not in key for key in app.conf.beat_schedule.keys())
    schedule = next(iter(app.conf.beat_schedule.values()))
    assert schedule["args"] == ("AAPL", "news_api")
    assert app.conf.worker_concurrency == 2
