"""Chat service for handling user messages and LLM streaming."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import AsyncIterator, Iterator, List, Optional, Callable

from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from api import db_models
from api.redis_cache import RedisSessionCache
from api.repositories import add_chat_message, list_chat_messages
from ingestion.services.chroma_client import ChromaClient, default_chroma_client, ChromaError
from llm.client.openai_client import OpenAIClient, PermanentLLMError, TransientLLMError
from llm.embeddings import embed_texts


class ChatServiceError(Exception):
    """채팅 스트리밍 오류를 표현."""

    def __init__(self, code: str, detail: str, trace_id: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.trace_id = trace_id


class ChatService:
    """Business logic for chat interactions."""

    HISTORY_LIMIT = 20
    STREAM_RETRY_LIMIT = 1

    def __init__(
        self,
        openai_client: OpenAIClient,
        redis_cache: RedisSessionCache,
        *,
        chroma_client: Optional[ChromaClient] = None,
        embedder: Optional[Callable[[List[str]], List[List[float]]]] = None,
        rag_enabled: Optional[bool] = None,
        rag_results: int = 5,
        rag_max_chars: int = 1600,
    ):
        self.openai_client = openai_client
        self.cache = redis_cache
        self.chroma = chroma_client
        self.embedder = embedder or (lambda texts: embed_texts(texts))
        self.rag_enabled = (
            rag_enabled
            if rag_enabled is not None
            else (os.getenv("CHAT_RAG_ENABLED", "false").lower() == "true")
        )
        self.rag_results = rag_results
        self.rag_max_chars = rag_max_chars
        self.logger = logging.getLogger(__name__)

    async def handle_message(
        self,
        db_session: Session,
        session_id: str,
        user_message: str,
    ) -> AsyncIterator[str]:
        trace_id = uuid.uuid4().hex
        message = user_message.strip()
        if not message:
            raise ChatServiceError("invalid_input", "메시지를 입력해주세요.", trace_id)

        try:
            add_chat_message(db_session, session_id, "user", message)
            db_session.commit()
        except NoResultFound as exc:
            raise ChatServiceError("session_not_found", "채팅 세션을 찾을 수 없습니다.", trace_id) from exc

        self._clear_cached_context(session_id)
        context = self._build_context(db_session, session_id, message, trace_id)

        full_response: list[str] = []
        async for chunk in self._stream_response(context, trace_id):
            full_response.append(chunk)
            yield chunk

        complete_response = "".join(full_response).strip()
        if complete_response:
            self._save_agent_message(db_session, session_id, complete_response)
            self._cache_context_with_reply(session_id, context, complete_response)

    async def _stream_response(
        self, context: List[dict], trace_id: str
    ) -> AsyncIterator[str]:
        attempts = 0
        while attempts <= self.STREAM_RETRY_LIMIT:
            attempts += 1
            try:
                stream_iter = self.openai_client.stream_chat(
                    messages=context,
                    max_cost_usd=float(self.openai_client.settings.analysis_cost_limit_usd),
                    request_timeout_seconds=float(
                        self.openai_client.settings.analysis_request_timeout_seconds
                    ),
                    retry_max_attempts=0,
                )
                async for chunk in self._consume_stream(stream_iter):
                    yield chunk
                return
            except PermanentLLMError as exc:
                self.logger.warning(
                    "chat.cost_limit",
                    extra={"trace_id": trace_id, "error": str(exc)},
                )
                raise ChatServiceError(
                    "cost_limit",
                    "비용 상한을 초과하여 응답을 종료했습니다. 메시지를 축약해 다시 시도해주세요.",
                    trace_id,
                ) from exc
            except TransientLLMError as exc:
                self.logger.warning(
                    "chat.transient_error",
                    extra={"trace_id": trace_id, "error": str(exc), "attempt": attempts},
                )
                if attempts <= self.STREAM_RETRY_LIMIT:
                    continue
                raise ChatServiceError(
                    "llm_unavailable",
                    "일시적 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                    trace_id,
                ) from exc
            except Exception as exc:
                self.logger.exception("chat.unexpected_error", extra={"trace_id": trace_id})
                raise ChatServiceError(
                    "internal_error", "요청 처리 중 오류가 발생했습니다.", trace_id
                ) from exc

    async def _consume_stream(self, stream_iter: Iterator[str]) -> AsyncIterator[str]:
        loop = asyncio.get_event_loop()

        def _get_next_chunk():
            try:
                return next(stream_iter), False
            except StopIteration:
                return None, True

        while True:
            chunk, done = await loop.run_in_executor(None, _get_next_chunk)
            if done:
                break
            if chunk:
                yield chunk

    def _build_context(
        self, db_session: Session, session_id: str, user_message: str, trace_id: str
    ) -> List[dict]:
        cached = self._get_cached_context(session_id)
        if cached:
            return cached

        chat_session = db_session.get(db_models.ChatSession, session_id)
        if not chat_session:
            raise ChatServiceError("session_not_found", "채팅 세션을 찾을 수 없습니다.", trace_id)

        report = db_session.get(db_models.ReportSnapshot, chat_session.insight_id)
        if not report:
            raise ChatServiceError("report_not_found", "관련 리포트를 찾을 수 없습니다.", trace_id)

        messages: List[dict] = [
            {
                "role": "system",
                "content": (
                    "You are a helpful financial assistant. Answer concisely "
                    f"using this report context.\nTicker: {report.ticker}\n"
                    f"Headline: {report.headline}\nSummary: {report.summary_text}"
                ),
            }
        ]

        contexts = self._maybe_fetch_rag_context(user_message, report, trace_id)
        for ctx in contexts:
            messages.append({"role": "system", "content": ctx})

        history = list_chat_messages(db_session, session_id)[-self.HISTORY_LIMIT :]
        for msg in history:
            role = "user" if msg.sender == "user" else "assistant"
            if msg.sender == "system":
                role = "system"
            messages.append({"role": role, "content": msg.content})

        self._set_cached_context(session_id, messages)
        return messages

    def _save_agent_message(self, db_session: Session, session_id: str, content: str) -> None:
        add_chat_message(db_session, session_id, "agent", content)
        db_session.commit()

    def _cache_context_with_reply(
        self, session_id: str, context: List[dict], agent_reply: str
    ) -> None:
        cached = list(context)
        cached.append({"role": "assistant", "content": agent_reply})
        self._set_cached_context(session_id, cached)

    def _maybe_fetch_rag_context(
        self, user_message: str, report: db_models.ReportSnapshot, trace_id: str
    ) -> List[str]:
        if not self.rag_enabled:
            return []
        if self.chroma is None:
            self.chroma = default_chroma_client()
        try:
            query_emb = self.embedder([user_message])[0]
            raw = self.chroma.query(
                query_embeddings=[query_emb],
                n_results=self.rag_results,
                where={"ticker": report.ticker},
            )
        except (ChromaError, Exception) as exc:
            self.logger.warning(
                "chat.rag_failed",
                extra={"trace_id": trace_id, "error": str(exc)},
            )
            return []

        ids = raw.get("ids", [[]])[0]
        metadatas = raw.get("metadatas", [[]])[0]
        contexts: List[str] = []
        total_chars = 0
        for meta in metadatas:
            if not meta:
                continue
            headline = meta.get("headline") or ""
            summary = meta.get("summary_text") or ""
            text = f"Context from report: {headline}\n{summary}"
            if total_chars + len(text) > self.rag_max_chars:
                break
            contexts.append(text)
            total_chars += len(text)
            if len(contexts) >= self.rag_results:
                break
        return contexts

    def _get_cached_context(self, session_id: str) -> Optional[List[dict]]:
        try:
            return self.cache.get_context(session_id)
        except Exception:
            return None

    def _set_cached_context(self, session_id: str, context: List[dict]) -> None:
        try:
            self.cache.set_context(session_id, context)
        except Exception:
            return None

    def _clear_cached_context(self, session_id: str) -> None:
        try:
            self.cache.clear_context(session_id)
        except Exception:
            return None


# Global instance (will be initialized in main.py)
chat_service: ChatService | None = None


def get_chat_service() -> ChatService:
    """Get the global chat service instance."""
    if chat_service is None:
        raise RuntimeError("ChatService not initialized")
    return chat_service
