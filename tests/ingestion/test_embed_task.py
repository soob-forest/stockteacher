from __future__ import annotations

import importlib
from pathlib import Path
import sys
from typing import List

import pytest


pytestmark = pytest.mark.skipif(sys.version_info < (3, 10), reason="Requires Python 3.10+ for annotations")


class _FakeChroma:
    def __init__(self) -> None:
        self.upserts: list[dict] = []
        self.calls = {"heartbeat": 0, "ensure": 0}
        self.collection = "reports"

    def heartbeat(self) -> None:
        self.calls["heartbeat"] += 1

    def ensure_collection(self) -> None:
        self.calls["ensure"] += 1

    def upsert(self, *, ids, embeddings, metadatas) -> None:
        self.upserts.append({"ids": ids, "embeddings": embeddings, "metadatas": metadatas})


def test_embed_reports_core_upserts_to_chroma(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # DB 설정
    db_url = f"sqlite:///{tmp_path}/api.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    api_db = importlib.reload(importlib.import_module("api.database"))
    api_db.init_db()

    from api.db_models import ReportSnapshot

    # 데이터 준비
    with api_db.get_session() as session:
        session.add(
            ReportSnapshot(
                insight_id="insight_test",
                ticker="AAPL",
                headline="Apple launches product",
                summary_text="New product summary",
                published_at=None,
                status="published",
                sentiment_score=0.1,
                anomaly_score=0.2,
                tags=["tag"],
                keywords=["apple", "launch"],
                source_refs=[],
                attachments=[],
            )
        )
        session.commit()

    fake_chroma = _FakeChroma()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def _fake_embed(texts: List[str], model: str) -> List[List[float]]:
        assert texts and model
        return [[0.1, 0.2, 0.3]]

    embed_module = importlib.reload(importlib.import_module("ingestion.tasks.embed"))
    monkeypatch.setattr(embed_module, "default_chroma_client", lambda: fake_chroma)
    monkeypatch.setattr(embed_module, "embed_texts", lambda texts, settings=None: _fake_embed(texts, "m"))

    inserted = embed_module.embed_reports_core(limit=10)

    assert inserted == 1
    assert fake_chroma.calls["heartbeat"] == 1
    assert fake_chroma.calls["ensure"] == 1
    assert fake_chroma.upserts
    upsert = fake_chroma.upserts[0]
    assert upsert["ids"] == ["insight_test"]
    assert upsert["embeddings"] == [[0.1, 0.2, 0.3]]
    assert upsert["metadatas"][0]["ticker"] == "AAPL"
