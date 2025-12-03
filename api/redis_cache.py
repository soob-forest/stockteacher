"""Redis-based session cache for chat contexts."""

from __future__ import annotations

import json
from typing import List, Optional

import redis
from redis.exceptions import RedisError


class RedisSessionCache:
    """Redis cache for chat session contexts."""

    def __init__(self, redis_url: str = "redis://localhost:6379/1"):
        """Initialize Redis client.

        Args:
            redis_url: Redis connection URL (default: redis://localhost:6379/1)
        """
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)
        self.ttl = 3600  # 1 hour

    def get_context(self, session_id: str) -> Optional[List[dict]]:
        """Retrieve chat context for a session.

        Args:
            session_id: Chat session ID

        Returns:
            List of message dicts or None if not cached
        """
        key = f"chat:context:{session_id}"
        try:
            data = self.client.get(key)
        except RedisError:
            return None
        return json.loads(data) if data else None

    def set_context(self, session_id: str, context: List[dict]):
        """Store chat context for a session.

        Args:
            session_id: Chat session ID
            context: List of message dicts to cache
        """
        key = f"chat:context:{session_id}"
        try:
            self.client.setex(key, self.ttl, json.dumps(context))
        except RedisError:
            return

    def clear_context(self, session_id: str):
        """Remove cached context for a session.

        Args:
            session_id: Chat session ID
        """
        key = f"chat:context:{session_id}"
        try:
            self.client.delete(key)
        except RedisError:
            return
