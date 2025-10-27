from __future__ import annotations

from typing import Dict

from ingestion.services.deduplicator import InMemoryKeyStore, RedisKeyStore


class FakeRedis:
    def __init__(self) -> None:
        self._store: Dict[str, str] = {}

    def exists(self, name: str) -> int:
        return 1 if name in self._store else 0

    def set(self, name: str, value: str, *, ex: int | None = None, nx: bool | None = None):
        if nx:
            if name in self._store:
                return None
            self._store[name] = value
            return True
        self._store[name] = value
        return True


def test_inmemory_keystore_basic():
    ks = InMemoryKeyStore()
    assert not ks.has("k1")
    ks.add("k1")
    assert ks.has("k1")


def test_redis_keystore_basic():
    client = FakeRedis()
    ks = RedisKeyStore(client, prefix="test", default_ttl_seconds=60)
    assert not ks.has("k1")
    ks.add("k1")
    assert ks.has("k1")
    # NX should prevent overwrite and behave idempotently
    ks.add("k1")
    assert ks.has("k1")

