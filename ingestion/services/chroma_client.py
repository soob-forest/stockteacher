"""Chroma HTTP 클라이언트 래퍼.

의도:
- httpx 기반으로 heartbeat/컬렉션 생성/업서트/삭제/검색을 제공한다.
- 외부 의존성 최소화를 위해 SDK 대신 REST 엔드포인트를 직접 호출한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import httpx


class ChromaError(Exception):
    """Chroma 호출 실패."""


class ChromaClient:
    """간단한 Chroma HTTP 클라이언트."""

    def __init__(
        self,
        base_url: str,
        collection: str,
        *,
        timeout: float = 5.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.collection = collection
        self.timeout = timeout
        self._client = client or httpx.Client(timeout=timeout)

    def heartbeat(self) -> None:
        resp = self._client.get(f"{self.base_url}/api/v1/heartbeat")
        self._raise_for_status(resp)

    def ensure_collection(self) -> None:
        resp = self._client.get(f"{self.base_url}/api/v1/collections/{self.collection}")
        if resp.status_code == 200:
            return
        if resp.status_code != 404:
            self._raise_for_status(resp)

        payload = {"name": self.collection, "metadata": {"hnsw:space": "cosine"}}
        create_resp = self._client.post(f"{self.base_url}/api/v1/collections", json=payload)
        self._raise_for_status(create_resp)

    def upsert(
        self,
        *,
        ids: Iterable[str],
        embeddings: Iterable[List[float]],
        metadatas: Optional[Iterable[Dict[str, Any]]] = None,
    ) -> None:
        payload: Dict[str, Any] = {
            "ids": list(ids),
            "embeddings": list(embeddings),
        }
        if metadatas is not None:
            payload["metadatas"] = list(metadatas)
        resp = self._client.post(
            f"{self.base_url}/api/v1/collections/{self.collection}/add",
            json=payload,
        )
        self._raise_for_status(resp)

    def delete(self, *, ids: Iterable[str]) -> None:
        payload = {"ids": list(ids)}
        resp = self._client.post(
            f"{self.base_url}/api/v1/collections/{self.collection}/delete",
            json=payload,
        )
        self._raise_for_status(resp)

    def query(
        self,
        *,
        query_embeddings: List[List[float]],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "query_embeddings": query_embeddings,
            "n_results": n_results,
        }
        if where:
            payload["where"] = where
        resp = self._client.post(
            f"{self.base_url}/api/v1/collections/{self.collection}/query",
            json=payload,
        )
        self._raise_for_status(resp)
        return resp.json()

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            raise ChromaError(f"Chroma 요청 실패: {exc.response.status_code} {detail}") from exc


def default_chroma_client() -> ChromaClient:
    import os

    base = os.getenv("CHROMA_URL", "http://localhost:8001")
    collection = os.getenv("CHROMA_COLLECTION", "reports")
    timeout = float(os.getenv("CHROMA_HTTP_TIMEOUT_SECONDS", "5"))
    return ChromaClient(base, collection, timeout=timeout)
