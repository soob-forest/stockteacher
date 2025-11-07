from __future__ import annotations

import importlib
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select


def _prepare_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ingestion_url = f"sqlite:///{tmp_path}/ingestion.db"
    portal_url = f"sqlite:///{tmp_path}/portal.db"
    monkeypatch.setenv("POSTGRES_DSN", ingestion_url)
    monkeypatch.setenv("DATABASE_URL", portal_url)

    from ingestion.settings import reset_settings_cache

    reset_settings_cache()

    ingestion_session_module = importlib.import_module("ingestion.db.session")
    api_database_module = importlib.import_module("api.database")

    ingestion_session = importlib.reload(ingestion_session_module)
    api_database = importlib.reload(api_database_module)

    api_database.init_db()

    from ingestion.db.models import Base as IngestionBase

    IngestionBase.metadata.create_all(bind=ingestion_session.get_engine())

    from api.db_models import Base as ApiBase, ReportSnapshot

    ApiBase.metadata.create_all(bind=api_database.engine)

    with api_database.get_session() as api_session:
        api_session.execute(delete(ReportSnapshot))

    return ingestion_session, api_database


def test_reports_endpoint_returns_materialized_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ingestion_session, api_database = _prepare_env(tmp_path, monkeypatch)

    from ingestion.db.models import ProcessedInsight

    generated_at = datetime(2025, 6, 15, 9, 30, tzinfo=timezone.utc)

    with ingestion_session.session_scope() as session:
        insight = ProcessedInsight(
            ticker="TSLA",
            summary_text="Tesla faces renewed battery supply pressure but maintains production targets.",
            keywords=["battery", "production", "targets"],
            sentiment_score=-0.28,
            anomalies=[{"label": "supply_chain", "score": 0.52}],
            source_refs=[{"title": "Reuters", "url": "https://example.com/tsla"}],
            generated_at=generated_at,
            llm_model="gpt-4o-mini",
            llm_tokens_prompt=980,
            llm_tokens_completion=260,
            llm_cost=0.11,
        )
        session.add(insight)
        session.flush()
        insight_id = str(insight.id)

    materializer = importlib.import_module("publish.materializer")
    materializer = importlib.reload(materializer)
    materializer.materialize_reports(limit=5)

    api_main = importlib.import_module("api.main")
    api_main = importlib.reload(api_main)

    client = TestClient(api_main.app)

    # List endpoint
    response = client.get("/api/reports")
    assert response.status_code == 200
    items = response.json()
    assert any(item["insight_id"] == insight_id for item in items)

    # Detail endpoint
    detail = client.get(f"/api/reports/{insight_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["insight_id"] == insight_id
    assert payload["ticker"] == "TSLA"
    assert payload["sentiment_score"] == pytest.approx(-0.28)
    assert payload["anomaly_score"] == pytest.approx(0.52)
    published = datetime.fromisoformat(payload["published_at"])
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    assert published == generated_at

    # Favorite toggle
    fav_put = client.put(f"/api/reports/{insight_id}/favorite")
    assert fav_put.status_code == 204

    fav_delete = client.delete(f"/api/reports/{insight_id}/favorite")
    assert fav_delete.status_code == 204

    from api.db_models import FavoriteReport

    with api_database.get_session() as api_session:
        favorites = list(
            api_session.execute(select(FavoriteReport)).scalars()
        )
        assert favorites == []
