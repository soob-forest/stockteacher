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
    monkeypatch.setenv("INGESTION_REDIS_URL", "redis://localhost:6379/0")

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
    assert payload["status"] == "published"
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

    # Hide report
    patch_resp = client.patch(
        f"/api/reports/{insight_id}/status",
        json={"status": "hidden"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "hidden"

    # Hidden should be excluded by default
    response_hidden = client.get("/api/reports")
    assert response_hidden.status_code == 200
    assert all(item["insight_id"] != insight_id for item in response_hidden.json())

    # Include hidden when requested
    response_all = client.get("/api/reports?status=all")
    assert response_all.status_code == 200
    assert any(item["insight_id"] == insight_id for item in response_all.json())


def test_reports_endpoint_supports_extended_filters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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
    materializer.materialize_reports(limit=10)

    api_main = importlib.import_module("api.main")
    api_main = importlib.reload(api_main)

    client = TestClient(api_main.app)

    # 티커 필터
    tickers_resp = client.get("/api/reports", params=[("tickers", "TSLA")])
    assert tickers_resp.status_code == 200
    assert all(item["ticker"] == "TSLA" for item in tickers_resp.json())

    # 키워드 필터
    keyword_resp = client.get("/api/reports", params=[("keywords", "production")])
    assert keyword_resp.status_code == 200
    assert any(item["insight_id"] == insight_id for item in keyword_resp.json())

    # 날짜 범위 필터 (등록된 TSLA만 해당)
    date_resp = client.get(
        "/api/reports",
        params=[
            ("date_from", "2025-06-15T00:00:00+00:00"),
            ("date_to", "2025-06-15T23:59:59+00:00"),
        ],
    )
    assert date_resp.status_code == 200
    ids = {item["insight_id"] for item in date_resp.json()}
    assert ids == {insight_id}

    # 긴급 필터 (anomaly_score >= 0.4)
    urgent_resp = client.get("/api/reports", params=[("urgent_only", "true")])
    assert urgent_resp.status_code == 200
    urgent_items = urgent_resp.json()
    assert len(urgent_items) >= 1
    for item in urgent_items:
        detail = client.get(f"/api/reports/{item['insight_id']}")
        assert detail.status_code == 200
        assert detail.json()["anomaly_score"] >= 0.4
