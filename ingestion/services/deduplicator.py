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

