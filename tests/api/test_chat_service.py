from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Dict, Iterator, List

import pytest

from api.chat_service import ChatService, ChatServiceError
from api.repositories import add_chat_message, create_chat_session, list_chat_messages
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


def _stream_provider(_: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    yield {"choices": [{"delta": {"content": "hello"}}]}
    yield {"choices": [{"delta": {"content": " world"}}]}


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
async def test_handle_message_streams_and_caches(api_database):
    cache = InMemoryCache()
    client = OpenAIClient.from_env(stream_provider=_stream_provider)
    service = ChatService(client, cache)

    with api_database.get_session() as session:
        chat = create_chat_session(session, "demo-user", "insight_a")
        session.commit()

        chunks: List[str] = []
        async for chunk in service.handle_message(session, chat.session_id, "안녕?"):
            chunks.append(chunk)

        assert "".join(chunks) == "hello world"
        history = list_chat_messages(session, chat.session_id)
        assert any(m.sender == "agent" and m.content == "hello world" for m in history)
        cached = cache.get_context(chat.session_id)
        assert cached is not None
        assert cached[-1]["content"] == "hello world"


@pytest.mark.asyncio
async def test_handle_message_missing_session_raises(api_database):
    client = OpenAIClient.from_env(stream_provider=_stream_provider)
    service = ChatService(client, InMemoryCache())

    with api_database.get_session() as session:
        with pytest.raises(ChatServiceError) as excinfo:
            async for _ in service.handle_message(session, "missing", "hi"):
                pass
        assert excinfo.value.code == "session_not_found"


@pytest.mark.asyncio
async def test_handle_message_cost_limit(api_database, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANALYSIS_COST_LIMIT_USD", "0.00001")
    reset_analysis_settings_cache()

    client = OpenAIClient.from_env(stream_provider=_stream_provider)
    service = ChatService(client, InMemoryCache())

    with api_database.get_session() as session:
        chat = create_chat_session(session, "demo-user", "insight_a")
        session.commit()
        with pytest.raises(ChatServiceError) as excinfo:
            async for _ in service.handle_message(
                session, chat.session_id, "길게" * 400
            ):
                pass
        assert excinfo.value.code == "cost_limit"


def test_build_context_limits_history_and_caches(api_database):
    cache = InMemoryCache()
    client = OpenAIClient.from_env(stream_provider=_stream_provider)
    service = ChatService(client, cache)

    with api_database.get_session() as session:
        chat = create_chat_session(session, "demo-user", "insight_a")
        # Add many messages to test trimming
        for i in range(25):
            sender = "user" if i % 2 == 0 else "agent"
            add_chat_message(session, chat.session_id, sender, f"msg-{i}")
        session.commit()

        context = service._build_context(session, chat.session_id, "trace-test")
        assert len(context) == 1 + 20  # system + 최근 20개
        assert context[-1]["content"] == "msg-24"
        assert cache.get_context(chat.session_id) is not None
