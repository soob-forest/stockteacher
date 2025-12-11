from __future__ import annotations

import json
from typing import Any, Dict, List

import httpx
import pytest

from ingestion.services.chroma_client import ChromaClient, ChromaError


def _mock_transport(respond):
    return httpx.MockTransport(respond)


def test_heartbeat_ok() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/api/v1/heartbeat")
        return httpx.Response(200, json={"status": "ok"})

    client = ChromaClient("http://chroma:8000", "reports", client=httpx.Client(transport=_mock_transport(respond)))
    client.heartbeat()  # no exception


def test_ensure_collection_existing_no_create() -> None:
    called = {"get": 0, "post": 0}

    def respond(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            called["get"] += 1
            return httpx.Response(200, json={"name": "reports"})
        if request.method == "POST":
            called["post"] += 1
        return httpx.Response(500)

    client = ChromaClient("http://chroma:8000", "reports", client=httpx.Client(transport=_mock_transport(respond)))
    client.ensure_collection()
    assert called["get"] == 1
    assert called["post"] == 0


def test_ensure_collection_creates_on_404() -> None:
    called = {"get": 0, "post": 0}

    def respond(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            called["get"] += 1
            return httpx.Response(404)
        if request.method == "POST":
            called["post"] += 1
            assert request.url.path.endswith("/api/v1/collections")
            payload = json.loads(request.content.decode())
            assert payload["name"] == "reports"
            return httpx.Response(201, json=payload)
        return httpx.Response(500)

    client = ChromaClient("http://chroma:8000", "reports", client=httpx.Client(transport=_mock_transport(respond)))
    client.ensure_collection()
    assert called["get"] == 1
    assert called["post"] == 1


def test_upsert_and_query_and_delete() -> None:
    seen: Dict[str, List[Dict[str, Any]]] = {"add": [], "delete": [], "query": []}

    def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/add"):
            payload = json.loads(request.content.decode())
            seen["add"].append(payload)
            return httpx.Response(200, json={"ids": payload["ids"]})
        if path.endswith("/delete"):
            payload = json.loads(request.content.decode())
            seen["delete"].append(payload)
            return httpx.Response(200, json={"ids": payload["ids"]})
        if path.endswith("/query"):
            payload = json.loads(request.content.decode())
            seen["query"].append(payload)
            return httpx.Response(
                200,
                json={
                    "ids": [["a1"]],
                    "distances": [[0.12]],
                    "embeddings": None,
                },
            )
        return httpx.Response(500)

    client = ChromaClient("http://chroma:8000", "reports", client=httpx.Client(transport=_mock_transport(respond)))
    client.upsert(ids=["a1"], embeddings=[[0.1, 0.2, 0.3]], metadatas=[{"ticker": "AAPL"}])
    result = client.query(query_embeddings=[[0.1, 0.2, 0.3]], n_results=3, where={"ticker": "AAPL"})
    client.delete(ids=["a1"])

    assert seen["add"][0]["ids"] == ["a1"]
    assert seen["add"][0]["embeddings"] == [[0.1, 0.2, 0.3]]
    assert seen["add"][0]["metadatas"] == [{"ticker": "AAPL"}]
    assert seen["query"][0]["n_results"] == 3
    assert seen["query"][0]["where"] == {"ticker": "AAPL"}
    assert seen["delete"][0]["ids"] == ["a1"]
    assert result["ids"] == [["a1"]]


def test_chroma_error_on_http_failure() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = ChromaClient("http://chroma:8000", "reports", client=httpx.Client(transport=_mock_transport(respond)))
    with pytest.raises(ChromaError):
        client.heartbeat()
