#!/usr/bin/env python3
"""Chroma 컬렉션 초기화 스크립트.

기능:
- Heartbeat 확인
- 컬렉션 존재 여부 확인 후 없으면 생성(distance=cosine)
환경 변수:
  CHROMA_URL (기본: http://localhost:8001)
  CHROMA_COLLECTION (기본: reports)
"""

from __future__ import annotations

import os
import sys
from typing import Tuple

import httpx


def _env() -> Tuple[str, str]:
    base = os.getenv("CHROMA_URL", "http://localhost:8001").rstrip("/")
    collection = os.getenv("CHROMA_COLLECTION", "reports").strip() or "reports"
    return base, collection


def _check_heartbeat(base_url: str) -> None:
    resp = httpx.get(f"{base_url}/api/v1/heartbeat", timeout=3.0)
    resp.raise_for_status()


def _ensure_collection(base_url: str, collection: str) -> bool:
    """컬렉션이 없으면 생성한다. 반환값: 새로 만들었는지 여부."""
    with httpx.Client(timeout=5.0) as client:
        resp = client.get(f"{base_url}/api/v1/collections/{collection}")
        if resp.status_code == 200:
            return False
        if resp.status_code not in (404,):
            resp.raise_for_status()
        payload = {"name": collection, "metadata": {"hnsw:space": "cosine"}}
        create_resp = client.post(f"{base_url}/api/v1/collections", json=payload)
        create_resp.raise_for_status()
        return True


def main() -> int:
    base_url, collection = _env()
    print(f"[init_chroma] base_url={base_url}, collection={collection}")
    try:
        _check_heartbeat(base_url)
        created = _ensure_collection(base_url, collection)
    except httpx.HTTPStatusError as exc:
        print(f"[init_chroma] HTTP 오류: {exc.response.status_code} {exc.response.text}", file=sys.stderr)
        return 1
    except httpx.RequestError as exc:
        print(f"[init_chroma] 요청 실패: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - 예기치 못한 오류
        print(f"[init_chroma] 예기치 못한 오류: {exc}", file=sys.stderr)
        return 1

    msg = "새 컬렉션 생성 완료" if created else "컬렉션 이미 존재"
    print(f"[init_chroma] 완료: {msg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
