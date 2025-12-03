from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _prepare_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_url = f"sqlite:///{tmp_path}/related.db"
    monkeypatch.setenv("DATABASE_URL", db_url)

    api_database_module = importlib.import_module("api.database")
    api_database = importlib.reload(api_database_module)
    api_database.init_db()

    from sqlalchemy import delete
    from api.db_models import ReportSnapshot

    with api_database.get_session() as session:
        session.execute(delete(ReportSnapshot))
        session.commit()

    return api_database


def test_related_reports_returns_scored_top3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    api_database = _prepare_api(tmp_path, monkeypatch)

    from api.db_models import ReportSnapshot

    now = datetime.now(timezone.utc)
    with api_database.get_session() as session:
        base = ReportSnapshot(
            insight_id="base_insight",
            ticker="TSLA",
            headline="Base report",
            summary_text="base summary",
            published_at=now - timedelta(hours=1),
            status="published",
            sentiment_score=0.1,
            anomaly_score=0.2,
            tags=["ev"],
            keywords=["battery", "supply"],
            source_refs=[],
            attachments=[],
        )
        c1 = ReportSnapshot(
            insight_id="cand_1",
            ticker="TSLA",  # same ticker bonus
            headline="Battery update",
            summary_text="c1",
            published_at=now - timedelta(hours=2),
            status="published",
            sentiment_score=0.2,
            anomaly_score=0.1,
            tags=["ev"],
            keywords=["battery"],
            source_refs=[],
            attachments=[],
        )
        c2 = ReportSnapshot(
            insight_id="cand_2",
            ticker="AAPL",
            headline="Supply chain news",
            summary_text="c2",
            published_at=now - timedelta(hours=3),
            status="published",
            sentiment_score=0.3,
            anomaly_score=0.1,
            tags=["supply"],
            keywords=["battery", "supply"],
            source_refs=[],
            attachments=[],
        )
        c3 = ReportSnapshot(
            insight_id="cand_3",
            ticker="MSFT",
            headline="Unrelated",
            summary_text="c3",
            published_at=now - timedelta(hours=4),
            status="published",
            sentiment_score=0.0,
            anomaly_score=0.1,
            tags=[],
            keywords=["cloud"],
            source_refs=[],
            attachments=[],
        )
        c4_old = ReportSnapshot(
            insight_id="cand_4",
            ticker="TSLA",
            headline="Old item",
            summary_text="c4",
            published_at=now - timedelta(days=10),
            status="published",
            sentiment_score=0.0,
            anomaly_score=0.1,
            tags=[],
            keywords=["battery"],
            source_refs=[],
            attachments=[],
        )
        session.add_all([base, c1, c2, c3, c4_old])
        session.commit()

    api_main = importlib.import_module("api.main")
    api_main = importlib.reload(api_main)
    client = TestClient(api_main.app)

    resp = client.get("/api/reports/base_insight/related")
    assert resp.status_code == 200
    payload = resp.json()

    # should exclude unrelated/old, include top by score: c2 (2 keywords) then c1 (1 keyword + ticker bonus)
    returned_ids = [item["insight_id"] for item in payload]
    assert returned_ids == ["cand_2", "cand_1"]
    assert all(item["status"] == "published" for item in payload)


def test_related_reports_returns_404_for_missing_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _ = _prepare_api(tmp_path, monkeypatch)
    api_main = importlib.import_module("api.main")
    api_main = importlib.reload(api_main)
    client = TestClient(api_main.app)

    resp = client.get("/api/reports/missing/related")
    assert resp.status_code == 404
