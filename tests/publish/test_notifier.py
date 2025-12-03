from __future__ import annotations

import importlib
from datetime import datetime, timezone
from pathlib import Path

import pytest


def _prepare_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    portal_url = f"sqlite:///{tmp_path}/portal.db"
    monkeypatch.setenv("DATABASE_URL", portal_url)
    api_database_module = importlib.import_module("api.database")
    api_database = importlib.reload(api_database_module)
    api_database.init_db()
    return api_database


def _make_snapshot(insight_id: str, **kwargs):
    from api.db_models import ReportSnapshot

    defaults = {
        "insight_id": insight_id,
        "ticker": "TSLA",
        "headline": "Headline",
        "summary_text": "Summary",
        "published_at": datetime.now(timezone.utc),
        "status": "published",
        "sentiment_score": 0.0,
        "anomaly_score": 0.0,
        "tags": [],
        "keywords": [],
        "source_refs": [],
        "attachments": [],
    }
    defaults.update(kwargs)
    return ReportSnapshot(**defaults)


def test_dispatches_for_urgent_anomaly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    api_database = _prepare_db(tmp_path, monkeypatch)
    from api.db_models import NotificationPolicy, StockSubscription
    from publish.notifier import dispatch_urgent_notifications

    with api_database.get_session() as session:
        session.add(
            StockSubscription(
                subscription_id="sub1",
                user_id="user-a",
                ticker="TSLA",
                alert_window="daily_close",
                status="Active",
            )
        )
        session.add(
            NotificationPolicy(
                policy_id="np1",
                user_id="user-a",
                timezone="Asia/Seoul",
                window="daily_close",
                frequency="daily",
                channels=["email", "web-push"],
                quiet_hours_start=None,
                quiet_hours_end=None,
            )
        )
        snapshot = _make_snapshot(
            "insight-urgent",
            anomaly_score=0.9,
            sentiment_score=-0.4,
        )
        session.add(snapshot)
        session.commit()

        dispatched = dispatch_urgent_notifications(session, snapshot)
        assert len(dispatched) == 1
        assert dispatched[0].user_id == "user-a"
        assert set(dispatched[0].channels) == {"email", "web-push"}
        assert dispatched[0].reason == "anomaly"


def test_dispatch_skips_quiet_hours(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    api_database = _prepare_db(tmp_path, monkeypatch)
    from api.db_models import NotificationPolicy, StockSubscription
    from publish.notifier import dispatch_urgent_notifications

    with api_database.get_session() as session:
        session.add(
            StockSubscription(
                subscription_id="sub2",
                user_id="user-b",
                ticker="TSLA",
                alert_window="daily_close",
                status="Active",
            )
        )
        session.add(
            NotificationPolicy(
                policy_id="np2",
                user_id="user-b",
                timezone="Asia/Seoul",
                window="daily_close",
                frequency="daily",
                channels=["email"],
                quiet_hours_start="09:00",
                quiet_hours_end="18:00",
            )
        )
        snapshot = _make_snapshot("insight-quiet", anomaly_score=0.8)
        session.add(snapshot)
        session.commit()

        # 01:00 UTC == 10:00 Asia/Seoul (within quiet hours)
        now = datetime(2025, 1, 1, 1, 0, tzinfo=timezone.utc)
        dispatched = dispatch_urgent_notifications(session, snapshot, now=now)
        assert dispatched == []


def test_non_urgent_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    api_database = _prepare_db(tmp_path, monkeypatch)
    from api.db_models import StockSubscription
    from publish.notifier import dispatch_urgent_notifications

    with api_database.get_session() as session:
        session.add(
            StockSubscription(
                subscription_id="sub3",
                user_id="user-c",
                ticker="TSLA",
                alert_window="daily_close",
                status="Active",
            )
        )
        snapshot = _make_snapshot("insight-normal", anomaly_score=0.2, sentiment_score=0.1)
        session.add(snapshot)
        session.commit()

        dispatched = dispatch_urgent_notifications(session, snapshot)
        assert dispatched == []
