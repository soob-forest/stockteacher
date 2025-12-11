"""OpenAI Embeddings 호출 래퍼.

Provider 주입이 가능해 테스트에서 네트워크 없이 결정적 동작을 검증할 수 있다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional

import httpx

EmbeddingProvider = Callable[[List[str], str], List[List[float]]]


class EmbeddingError(Exception):
    """임베딩 생성 실패."""


@dataclass(frozen=True)
class EmbeddingSettings:
    model: str
    request_timeout_seconds: float

    @classmethod
    def from_env(cls) -> "EmbeddingSettings":
        return cls(
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            request_timeout_seconds=float(os.getenv("EMBEDDING_REQUEST_TIMEOUT_SECONDS", "10")),
        )


def _default_provider(texts: List[str], model: str) -> List[List[float]]:
    """OpenAI Python SDK 없이 REST API로 embeddings를 호출한다."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise EmbeddingError("OPENAI_API_KEY가 설정되지 않았습니다.")

    url = "https://api.openai.com/v1/embeddings"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"input": texts, "model": model}
    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data.get("data", [])]
    except Exception as exc:
        raise EmbeddingError(f"임베딩 요청 실패: {exc}") from exc


def embed_texts(
    texts: Iterable[str],
    *,
    settings: Optional[EmbeddingSettings] = None,
    provider: Optional[EmbeddingProvider] = None,
) -> List[List[float]]:
    """텍스트 리스트를 임베딩으로 변환한다."""
    settings = settings or EmbeddingSettings.from_env()
    payload = [t for t in texts if t.strip()]
    if not payload:
        raise EmbeddingError("임베딩할 텍스트가 없습니다.")
    embed = provider or _default_provider
    return embed(payload, settings.model)
