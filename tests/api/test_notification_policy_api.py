from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from llm.settings import reset_analysis_settings_cache

from api.models import DEFAULT_NOTIFICATION_POLICY


def _prepare_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/notification.db")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    reset_analysis_settings_cache()

    api_database_module = importlib.import_module("api.database")
    api_database = importlib.reload(api_database_module)
    api_database.init_db()

    api_main = importlib.import_module("api.main")
    api_main = importlib.reload(api_main)
    return TestClient(api_main.app)


def test_get_notification_policy_returns_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = _prepare_api(tmp_path, monkeypatch)

    resp = client.get("/api/notifications/policy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "demo-user"
    assert data["timezone"] == DEFAULT_NOTIFICATION_POLICY["timezone"]
    assert data["window"] == DEFAULT_NOTIFICATION_POLICY["window"]
    assert data["frequency"] == DEFAULT_NOTIFICATION_POLICY["frequency"]
    assert data["channels"] == DEFAULT_NOTIFICATION_POLICY["channels"]
    assert data["quiet_hours_start"] is None
    assert data["quiet_hours_end"] is None


def test_upsert_notification_policy_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = _prepare_api(tmp_path, monkeypatch)
    payload = {
        "timezone": "Europe/London",
        "window": "morning_open",
        "frequency": "weekly",
        "channels": ["email", "web-push"],
        "quiet_hours_start": "08:00",
        "quiet_hours_end": "18:00",
    }

    put_resp = client.put("/api/notifications/policy", json=payload)
    assert put_resp.status_code == 200
    returned = put_resp.json()
    assert returned["timezone"] == payload["timezone"]
    assert returned["window"] == payload["window"]
    assert returned["frequency"] == payload["frequency"]
    assert returned["channels"] == payload["channels"]
    assert returned["quiet_hours_start"] == payload["quiet_hours_start"]
    assert returned["quiet_hours_end"] == payload["quiet_hours_end"]

    get_resp = client.get("/api/notifications/policy")
    assert get_resp.status_code == 200
    assert get_resp.json() == returned


def test_upsert_notification_policy_rejects_invalid_timezone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = _prepare_api(tmp_path, monkeypatch)
    payload = {
        "timezone": "Mars/Phobos",
        "window": "daily_close",
        "frequency": "daily",
        "channels": ["email"],
    }

    resp = client.put("/api/notifications/policy", json=payload)
    assert resp.status_code == 422


def test_upsert_notification_policy_rejects_empty_channels(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = _prepare_api(tmp_path, monkeypatch)
    payload = {
        "timezone": "Asia/Seoul",
        "window": "daily_close",
        "frequency": "daily",
        "channels": [],
    }

    resp = client.put("/api/notifications/policy", json=payload)
    assert resp.status_code == 422


def test_upsert_notification_policy_rejects_invalid_quiet_hours(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = _prepare_api(tmp_path, monkeypatch)
    payload = {
        "timezone": "Asia/Tokyo",
        "window": "daily_close",
        "frequency": "daily",
        "channels": ["email"],
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "06:00",
    }

    resp = client.put("/api/notifications/policy", json=payload)
    assert resp.status_code == 422


def test_list_timezones_returns_presets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = _prepare_api(tmp_path, monkeypatch)

    resp = client.get("/api/notifications/timezones")
    assert resp.status_code == 200
    data = resp.json()
    assert "Asia/Seoul" in data
    assert "America/New_York" in data
