import json

import pytest

from ingestion.settings import get_settings, reset_settings_cache


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    reset_settings_cache()
    yield
    reset_settings_cache()


def _set_required_env(monkeypatch, **overrides):
    defaults = {
        "INGESTION_REDIS_URL": "redis://localhost:6379/0",
        "NEWS_API_KEY": "secret-key",
        "POSTGRES_DSN": "postgresql://user:pass@localhost:5432/app",
        "LOCAL_STORAGE_ROOT": "./var/storage",
        "COLLECTION_SCHEDULES": json.dumps(
            [
                {
                    "ticker": "AAPL",
                    "source": "news_api",
                    "interval_minutes": 5,
                    "enabled": True,
                }
            ]
        ),
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        monkeypatch.setenv(key, value)


def test_get_settings_reads_environment(monkeypatch):
    _set_required_env(monkeypatch)

    settings = get_settings()

    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.news_api_key and settings.news_api_key.get_secret_value() == "secret-key"
    assert settings.collection_schedules[0].ticker == "AAPL"
    assert settings.collection_schedules[0].interval_minutes == 5
    assert settings.local_storage_root.endswith("var/storage")


def test_reset_settings_cache_reloads(monkeypatch):
    _set_required_env(monkeypatch, NEWS_API_KEY="first-key")
    first = get_settings()
    assert first.news_api_key and first.news_api_key.get_secret_value() == "first-key"

    monkeypatch.setenv("NEWS_API_KEY", "next-key")
    second = get_settings()
    assert second.news_api_key and second.news_api_key.get_secret_value() == "first-key"

    reset_settings_cache()
    reloaded = get_settings()
    assert reloaded.news_api_key and reloaded.news_api_key.get_secret_value() == "next-key"


def test_duplicate_schedule_raises(monkeypatch):
    duplicate_schedule = json.dumps(
        [
            {"ticker": "AAPL", "source": "news_api", "interval_minutes": 5},
            {"ticker": "AAPL", "source": "news_api", "interval_minutes": 10},
        ]
    )
    _set_required_env(monkeypatch, COLLECTION_SCHEDULES=duplicate_schedule)

    with pytest.raises(RuntimeError) as exc:
        get_settings()

    assert "중복된 스케줄 항목" in str(exc.value)
