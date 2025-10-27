"""Deduplication helpers with pluggable keystore (Redis-like)."""

from __future__ import annotations

from typing import Protocol


class KeyStore(Protocol):
    def has(self, key: str) -> bool: ...  # noqa: D401
    def add(self, key: str, ttl_seconds: int | None = None) -> None: ...  # noqa: D401


class InMemoryKeyStore:
    """Simple in-memory keystore for tests/local runs."""

    def __init__(self) -> None:
        self._set: set[str] = set()

    def has(self, key: str) -> bool:  # pragma: no cover - trivial
        return key in self._set

    def add(self, key: str, ttl_seconds: int | None = None) -> None:  # pragma: no cover - trivial
        self._set.add(key)


class _RedisLikeClient(Protocol):
    def exists(self, name: str) -> int: ...  # returns 1 if exists, else 0
    def set(self, name: str, value: str, *, ex: int | None = None, nx: bool | None = None) -> bool | None: ...


class RedisKeyStore:
    """Redis 기반 KeyStore 구현.

    - 존재 확인: `EXISTS key` → 정수(0/1)
    - 추가: `SET key value NX EX <ttl>` → 키가 없을 때만 설정, TTL 선택

    주의: 이 구현은 redis-py 클라이언트 호환 인터페이스를 기대하지만, 테스트에서는
    간단한 fake 클라이언트를 주입하여 외부 의존성 없이 검증합니다.
    """

    def __init__(self, client: _RedisLikeClient, *, prefix: str = "dedup", default_ttl_seconds: int | None = None) -> None:
        self._client = client
        self._prefix = prefix
        self._default_ttl = default_ttl_seconds

    def _format(self, key: str) -> str:  # pragma: no cover - trivial
        return f"{self._prefix}:{key}"

    def has(self, key: str) -> bool:
        return bool(self._client.exists(self._format(key)))

    def add(self, key: str, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        # redis-py: set(name, value, ex=seconds, nx=True) returns True if set, None if not set
        _ = self._client.set(self._format(key), "1", ex=ttl, nx=True)
