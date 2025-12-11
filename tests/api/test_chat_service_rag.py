from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Dict, Iterator, List
import sys

import pytest

if sys.version_info < (3, 10):
    pytest.skip("Python 3.10+ required for annotations in api.models", allow_module_level=True)

from api.chat_service import ChatService
from api.repositories import create_chat_session
from llm.client.openai_client import OpenAIClient
from llm.settings import reset_analysis_settings_cache


class InMemoryCache:
    def __init__(self):
        self.store: Dict[str, List[dict]] = {}

    def get_context(self, session_id: str):
        return self.store.get(session_id)

    def set_context(self, session_id: str, context: List[dict]):
        self.store[session_id] = context

    def clear_context(self, session_id: str):
        self.store.pop(session_id, None)


class _FakeChroma:
    def query(self, *, query_embeddings, n_results, where=None):
        return {
            "ids": [["c1"]],
            "distances": [[0.2]],
            "metadatas": [[{"headline": "ctx", "summary_text": "context summary"}]],
        }


def _stream_provider(_: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    yield {"choices": [{"delta": {"content": "ok"}}]}


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch):
    reset_analysis_settings_cache()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    monkeypatch.setenv("ANALYSIS_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("ANALYSIS_MAX_TOKENS", "128")
    monkeypatch.setenv("ANALYSIS_TEMPERATURE", "0.2")
    monkeypatch.setenv("ANALYSIS_REQUEST_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("ANALYSIS_RETRY_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("ANALYSIS_COST_LIMIT_USD", "0.05")
    yield
    reset_analysis_settings_cache()


@pytest.fixture
def api_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/chat.db")
    api_database_module = importlib.import_module("api.database")
    api_database = importlib.reload(api_database_module)
    api_database.init_db()
    return api_database


@pytest.mark.asyncio
async def test_handle_message_includes_rag_context(api_database):
    cache = InMemoryCache()
    client = OpenAIClient.from_env(stream_provider=_stream_provider)
    service = ChatService(
        client,
        cache,
        chroma_client=_FakeChroma(),
        embedder=lambda texts: [[0.1, 0.2, 0.3] for _ in texts],
        rag_enabled=True,
        rag_results=2,
        rag_max_chars=500,
    )

    with api_database.get_session() as session:
        chat = create_chat_session(session, "demo-user", "insight_a")
        session.commit()

        chunks: List[str] = []
        async for chunk in service.handle_message(session, chat.session_id, "안녕?"):
            chunks.append(chunk)

        assert "".join(chunks) == "ok"
        cached = cache.get_context(chat.session_id)
        assert cached is not None
        # 시스템 컨텍스트 + RAG 컨텍스트 + 히스토리 2개(사용자/에이전트)
        assert any("context summary" in msg["content"] for msg in cached if msg["role"] == "system")
