from __future__ import annotations

import os
from dataclasses import dataclass
import logging
import time
from typing import Callable, Dict, Iterable, List, Sequence
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from api import db_models
from api.models import ReportSummary
from api.repositories import to_report_summary
from ingestion.services.chroma_client import ChromaClient, default_chroma_client
from llm.embeddings import embed_texts


def compute_hybrid_score(
    vector_score: float,
    *,
    ticker_match: bool,
    keyword_overlap: int,
    ticker_weight: float,
    keyword_weight: float,
) -> float:
    score = vector_score
    if ticker_match:
        score += ticker_weight
    if keyword_overlap:
        score += keyword_weight * keyword_overlap
    return score


@dataclass
class SearchFilters:
    tickers: list[str] | None = None
    keywords: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None
    limit: int = 10


class VectorSearchService:
    def __init__(
        self,
        chroma_client: ChromaClient | None = None,
        embedder: Callable[[Iterable[str]], List[List[float]]] | None = None,
    ) -> None:
        self.chroma = chroma_client or default_chroma_client()
        self.embedder = embedder or (lambda texts: embed_texts(texts))
        self.ticker_weight = float(os.getenv("VECTOR_TICKER_WEIGHT", "0.2"))
        self.keyword_weight = float(os.getenv("VECTOR_KEYWORD_WEIGHT", "0.1"))
        self.logger = logging.getLogger(__name__)

    def _embed(self, text: str) -> List[float]:
        return self.embedder([text])[0]

    def related_reports(
        self,
        session: Session,
        base: db_models.ReportSnapshot,
        user_id: str,
        limit: int = 3,
    ) -> list[ReportSummary]:
        text = f"{base.headline}\n{base.summary_text}"
        embedding = self._embed(text)
        start = time.perf_counter()

        try:
            self.chroma.heartbeat()
            raw = self.chroma.query(
                query_embeddings=[embedding],
                n_results=max(1, limit * 4),
                where={"status": {"$ne": "hidden"}},
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            self.logger.warning(
                "vector.related.fallback",
                extra={"trace_id": _trace_id(), "reason": str(exc), "duration_ms": duration_ms},
            )
            return self._fallback_related(session, base, user_id, limit)

        ids = raw.get("ids", [[]])[0]
        distances = raw.get("distances", [[]])[0]
        metadatas = raw.get("metadatas", [[]])[0]
        if not ids:
            return self._fallback_related(session, base, user_id, limit)

        snapshots: Sequence[db_models.ReportSnapshot] = session.scalars(
            select(db_models.ReportSnapshot).where(db_models.ReportSnapshot.insight_id.in_(ids))
        ).unique().all()
        snapshot_map = {row.insight_id: row for row in snapshots}
        base_keywords = {kw.lower() for kw in (base.keywords or [])}

        results: list[tuple[float, db_models.ReportSnapshot]] = []
        for insight_id, dist, meta in zip(ids, distances, metadatas):
            if insight_id == base.insight_id:
                continue
            snap = snapshot_map.get(insight_id)
            if not snap:
                continue
            meta_keywords = {k.lower() for k in (meta or {}).get("keywords", [])}
            overlap = len(base_keywords.intersection(meta_keywords))
            vector_score = 1 - float(dist)
            score = compute_hybrid_score(
                vector_score,
                ticker_match=snap.ticker == base.ticker,
                keyword_overlap=overlap,
                ticker_weight=self.ticker_weight,
                keyword_weight=self.keyword_weight,
            )
            results.append((score, snap))

        results.sort(key=lambda pair: (pair[0], pair[1].published_at), reverse=True)
        favorites = set(
            session.scalars(
                select(db_models.FavoriteReport.insight_id).where(db_models.FavoriteReport.user_id == user_id)
            )
        )
        return [
            to_report_summary(row, row.insight_id in favorites)
            for score, row in results[:limit]
        ]

    def search_reports(
        self,
        session: Session,
        query: str,
        user_id: str,
        filters: SearchFilters,
    ) -> list[ReportSummary]:
        if not query.strip():
            return []

        embedding = self.embedder([query])[0]
        where: Dict[str, object] = {}
        if filters.tickers:
            where["ticker"] = {"$in": [t.upper() for t in filters.tickers]}
        if filters.keywords:
            where["keywords"] = {"$contains": filters.keywords}

        start = time.perf_counter()
        try:
            self.chroma.heartbeat()
            raw = self.chroma.query(
                query_embeddings=[embedding],
                n_results=max(1, filters.limit * 2),
                where=where or None,
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            self.logger.warning(
                "vector.search.fallback",
                extra={"trace_id": _trace_id(), "reason": str(exc), "duration_ms": duration_ms},
            )
            return self._fallback_search(session, query, user_id, filters)

        ids = raw.get("ids", [[]])[0]
        distances = raw.get("distances", [[]])[0]
        metadatas = raw.get("metadatas", [[]])[0]
        if not ids:
            return self._fallback_search(session, query, user_id, filters)

        snapshots: Sequence[db_models.ReportSnapshot] = session.scalars(
            select(db_models.ReportSnapshot).where(db_models.ReportSnapshot.insight_id.in_(ids))
        ).unique().all()
        snapshot_map = {row.insight_id: row for row in snapshots}

        return self._score_and_slice(
            ids=ids,
            distances=distances,
            metadatas=metadatas,
            snapshot_map=snapshot_map,
            user_id=user_id,
            filters=filters,
            session=session,
        )

    def _score_and_slice(
        self,
        *,
        ids: list[str],
        distances: list[float],
        metadatas: list[dict],
        snapshot_map: dict[str, db_models.ReportSnapshot],
        user_id: str,
        filters: SearchFilters,
        session: Session,
    ) -> list[ReportSummary]:
        filter_keywords = set(k.lower() for k in (filters.keywords or []))
        results: list[tuple[float, db_models.ReportSnapshot]] = []
        for insight_id, dist, meta in zip(ids, distances, metadatas):
            snap = snapshot_map.get(insight_id)
            if not snap:
                continue
            meta_keywords = set(k.lower() for k in (meta or {}).get("keywords", []))
            overlap = len(meta_keywords.intersection(filter_keywords)) if filter_keywords else 0
            vector_score = 1 - float(dist)
            score = compute_hybrid_score(
                vector_score,
                ticker_match=bool(filters.tickers and snap.ticker in filters.tickers),
                keyword_overlap=overlap,
                ticker_weight=self.ticker_weight,
                keyword_weight=self.keyword_weight,
            )
            results.append((score, snap))

        results.sort(key=lambda pair: (pair[0], pair[1].published_at), reverse=True)
        favorites = set(
            session.scalars(
                select(db_models.FavoriteReport.insight_id).where(db_models.FavoriteReport.user_id == user_id)
            )
        )
        return [
            to_report_summary(row, row.insight_id in favorites)
            for score, row in results[: filters.limit]
        ]

    def _fallback_related(
        self,
        session: Session,
        base: db_models.ReportSnapshot,
        user_id: str,
        limit: int,
    ) -> list[ReportSummary]:
        base_keywords = {kw.lower() for kw in (base.keywords or [])}
        rows: Sequence[db_models.ReportSnapshot] = session.scalars(
            select(db_models.ReportSnapshot)
            .where(db_models.ReportSnapshot.insight_id != base.insight_id)
            .where(db_models.ReportSnapshot.status != "hidden")
            .order_by(db_models.ReportSnapshot.published_at.desc())
            .limit(max(10, limit * 3))
        ).unique().all()
        scored: list[tuple[int, db_models.ReportSnapshot]] = []
        for row in rows:
            overlap = len(base_keywords.intersection({kw.lower() for kw in (row.keywords or [])}))
            ticker_match = 1 if row.ticker == base.ticker else 0
            score = overlap * 2 + ticker_match
            if score == 0:
                continue
            scored.append((score, row))
        scored.sort(key=lambda pair: (pair[0], pair[1].published_at), reverse=True)
        favorites = set(
            session.scalars(
                select(db_models.FavoriteReport.insight_id).where(db_models.FavoriteReport.user_id == user_id)
            )
        )
        return [
            to_report_summary(row, row.insight_id in favorites)
            for score, row in scored[:limit]
        ]

    def _fallback_search(
        self,
        session: Session,
        query: str,
        user_id: str,
        filters: SearchFilters,
    ) -> list[ReportSummary]:
        text_like = f"%{query}%"
        stmt = (
            select(db_models.ReportSnapshot)
            .where(db_models.ReportSnapshot.status != "hidden")
            .where(
                (db_models.ReportSnapshot.headline.ilike(text_like))
                | (db_models.ReportSnapshot.summary_text.ilike(text_like))
            )
        )
        if filters.tickers:
            stmt = stmt.where(db_models.ReportSnapshot.ticker.in_(filters.tickers))

        rows: Sequence[db_models.ReportSnapshot] = session.scalars(
            stmt.order_by(db_models.ReportSnapshot.published_at.desc()).limit(filters.limit)
        ).unique().all()
        favorites = set(
            session.scalars(
                select(db_models.FavoriteReport.insight_id).where(db_models.FavoriteReport.user_id == user_id)
            )
        )
        filtered: list[db_models.ReportSnapshot] = []
        for row in rows:
            if filters.keywords:
                row_keywords = {kw.lower() for kw in (row.keywords or [])}
                if not row_keywords.intersection({kw.lower() for kw in filters.keywords}):
                    continue
            filtered.append(row)
        return [to_report_summary(row, row.insight_id in favorites) for row in filtered[: filters.limit]]


_default_service: VectorSearchService | None = None


def get_vector_search_service() -> VectorSearchService:
    global _default_service
    if _default_service is None:
        _default_service = VectorSearchService()
    return _default_service


def _trace_id() -> str:
    return uuid4().hex
