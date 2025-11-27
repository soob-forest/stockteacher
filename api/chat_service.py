"""Chat service for handling user messages and LLM streaming."""

from __future__ import annotations

from typing import AsyncIterator, List

from sqlalchemy.orm import Session

from api import db_models
from api.redis_cache import RedisSessionCache
from api.repositories import add_chat_message, list_chat_messages
from llm.client.openai_client import OpenAIClient


class ChatService:
    """Business logic for chat interactions."""

    def __init__(self, openai_client: OpenAIClient, redis_cache: RedisSessionCache):
        """Initialize chat service.

        Args:
            openai_client: OpenAI client for LLM calls
            redis_cache: Redis cache for session contexts
        """
        self.openai_client = openai_client
        self.cache = redis_cache

    async def handle_message(
        self,
        db_session: Session,
        session_id: str,
        user_message: str,
    ) -> AsyncIterator[str]:
        """Process user message and stream LLM response.

        Args:
            db_session: Database session
            session_id: Chat session ID
            user_message: User's message content

        Yields:
            str: LLM response chunks

        Flow:
            1. Save user message to DB
            2. Build context (report summary + conversation history)
            3. Stream LLM response
            4. Save complete response to DB
        """
        # 1. Save user message
        add_chat_message(db_session, session_id, "user", user_message)
        db_session.commit()

        # 2. Build context
        context = self._build_context(db_session, session_id)

        # 3. Stream LLM response
        full_response = []
        for chunk in self.openai_client.stream_chat(messages=context):
            full_response.append(chunk)
            yield chunk

        # 4. Save agent response
        complete_response = "".join(full_response)
        if complete_response:
            add_chat_message(db_session, session_id, "agent", complete_response)
            db_session.commit()

    def _build_context(self, db_session: Session, session_id: str) -> List[dict]:
        """Build chat context for LLM.

        Args:
            db_session: Database session
            session_id: Chat session ID

        Returns:
            List of message dicts in OpenAI format:
            [
                {"role": "system", "content": "Report summary: ..."},
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."},
                ...
            ]
        """
        # Get chat session and related report
        chat_session = db_session.get(db_models.ChatSession, session_id)
        if not chat_session:
            return []

        report = db_session.get(db_models.ReportSnapshot, chat_session.insight_id)
        if not report:
            return []

        # System message with report summary
        messages = [
            {
                "role": "system",
                "content": f"You are a helpful financial assistant. The user is asking about this stock report:\n\nTicker: {report.ticker}\nHeadline: {report.headline}\nSummary: {report.summary_text}",
            }
        ]

        # Add conversation history (last 10 messages)
        history = list_chat_messages(db_session, session_id)[-10:]
        for msg in history:
            role = "user" if msg.sender == "user" else "assistant"
            messages.append({"role": role, "content": msg.content})

        return messages


# Global instance (will be initialized in main.py)
chat_service: ChatService | None = None


def get_chat_service() -> ChatService:
    """Get the global chat service instance."""
    if chat_service is None:
        raise RuntimeError("ChatService not initialized")
    return chat_service
