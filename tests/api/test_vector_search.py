from __future__ import annotations

import importlib
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List

from fastapi.testclient import TestClient
import pytest


pytestmark = pytest.mark.skipif(sys.version_info < (3, 10), reason="Requires Python 3.10+ for annotations")


class _FakeChroma:
    def __init__(self) -> None:
        self.queries: list[Dict[str, Any]] = []

    def query(self, *, query_embeddings, n_results, where=None):
        self.queries.append({"emb": query_embeddings, "n_results": n_results, "where": where})
        return {
            "ids": [["a1", "a2"]],
            "distances": [[0.2, 0.5]],
            "metadatas": [
                [
                    {"keywords": ["battery", "supply"], "ticker": "TSLA"},
                    {"keywords": ["cloud"], "ticker": "MSFT"},
                ]
            ],
        }

    def heartbeat(self):
        return None

    def ensure_collection(self):
        return None


def _fake_embed(texts: Iterable[str]) -> List[List[float]]:
    return [[0.1, 0.2, 0.3] for _ in texts]


def test_vector_search_service_ranks_and_filters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_url = f"sqlite:///{tmp_path}/vec.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    api_db = importlib.reload(importlib.import_module("api.database"))
    api_db.init_db()

    from api.db_models import ReportSnapshot

    with api_db.get_session() as session:
        session.add_all(
            [
                ReportSnapshot(
                    insight_id="a1",
                    ticker="TSLA",
                    headline="Battery update",
                    summary_text="news",
                    published_at=None,
                    status="published",
                    sentiment_score=0.1,
                    anomaly_score=0.2,
                    tags=["ev"],
                    keywords=["battery", "supply"],
                    source_refs=[],
                    attachments=[],
                ),
                ReportSnapshot(
                    insight_id="a2",
                    ticker="MSFT",
                    headline="Cloud news",
                    summary_text="news",
                    published_at=None,
                    status="published",
                    sentiment_score=0.1,
                    anomaly_score=0.1,
                    tags=["cloud"],
                    keywords=["cloud"],
                    source_refs=[],
                    attachments=[],
                ),
            ]
        )
        session.commit()

    vec_module = importlib.reload(importlib.import_module("api.vector_search"))
    service = vec_module.VectorSearchService(chroma_client=_FakeChroma(), embedder=_fake_embed)
    filters = vec_module.SearchFilters(tickers=["TSLA"], keywords=["battery"], limit=5)

    with api_db.get_session() as session:
        results = service.search_reports(session, "배터리", "demo-user", filters)

    assert len(results) == 2
    # TSLA with keyword overlap and ticker bonus should rank higher
    assert results[0].insight_id == "a1"
    assert results[1].insight_id == "a2"


def test_search_endpoint_uses_vector_service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # 주입: fake service가 고정 결과 반환
    fake_result = []

    class _FakeService:
        def search_reports(self, session, query, user_id, filters):
            fake_result.append({"query": query, "filters": filters})
            return []

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/api.db")
    api_main = importlib.reload(importlib.import_module("api.main"))
    # 의존성 주입
    import api.vector_search as vector_search

    vector_search_service = _FakeService()
    monkeypatch.setattr(vector_search, "_default_service", vector_search_service)

    client = TestClient(api_main.app)
    resp = client.get("/api/search", params={"query": "test"})
    assert resp.status_code == 200
    assert fake_result
