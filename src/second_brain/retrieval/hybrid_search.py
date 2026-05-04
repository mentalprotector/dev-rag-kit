"""Hybrid BM25 and vector search with Reciprocal Rank Fusion."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from typing import Protocol

from rank_bm25 import BM25Okapi

from second_brain.ingestion.schemas import DocumentChunk
from second_brain.retrieval.models import RetrievalResult

logger = logging.getLogger(__name__)

EmbedQueryFn = Callable[[str], Sequence[float]]


class VectorSearchBackend(Protocol):
    """Protocol for vector stores used by hybrid search."""

    def search(self, query_vector: Sequence[float], limit: int = 10) -> list[RetrievalResult]:
        """Return dense retrieval results."""


class HybridSearchEngine:
    """Combine sparse BM25 and dense vector retrieval into one ranked list."""

    def __init__(
        self,
        vector_store: VectorSearchBackend,
        documents: Sequence[DocumentChunk],
        embed_query: EmbedQueryFn,
        rrf_k: int = 60,
        vector_weight: float = 1.0,
        bm25_weight: float = 1.0,
    ) -> None:
        """Initialize hybrid search over a local chunk corpus and Qdrant vector store."""

        if rrf_k < 1:
            raise ValueError("rrf_k must be at least 1")
        self.vector_store = vector_store
        self.documents = list(documents)
        self.embed_query = embed_query
        self.rrf_k = rrf_k
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self._tokenized_corpus = [self._tokenize(chunk.content) for chunk in self.documents]
        self._bm25 = BM25Okapi(self._tokenized_corpus) if self.documents else None

    def search(self, query: str, limit: int = 10, vector_limit: int | None = None) -> list[RetrievalResult]:
        """Run dense and sparse retrieval, then merge using Reciprocal Rank Fusion."""

        if not query.strip():
            raise ValueError("query must not be empty")
        if limit < 1:
            raise ValueError("limit must be at least 1")

        candidate_limit = vector_limit or max(limit * 3, limit)
        query_vector = self.embed_query(query)
        vector_results = self.vector_store.search(query_vector, limit=candidate_limit)
        bm25_results = self._bm25_search(query, limit=candidate_limit)

        fused = self._reciprocal_rank_fusion(vector_results, bm25_results)
        logger.info(
            "Hybrid search completed vector=%s bm25=%s fused=%s",
            len(vector_results),
            len(bm25_results),
            len(fused),
        )
        return fused[:limit]

    def _bm25_search(self, query: str, limit: int) -> list[RetrievalResult]:
        """Return top BM25 matches from the local chunk corpus."""

        if self._bm25 is None:
            return []

        scores = self._bm25.get_scores(self._tokenize(query))
        ranked_indices = sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)
        results: list[RetrievalResult] = []
        for index in ranked_indices[:limit]:
            score = float(scores[index])
            if score <= 0:
                continue
            chunk = self.documents[index]
            results.append(
                RetrievalResult(
                    id=str(chunk.id),
                    content=chunk.content,
                    source=chunk.source,
                    metadata=chunk.metadata,
                    document_id=chunk.document_id,
                    chunk_index=chunk.chunk_index,
                    timestamp=chunk.timestamp,
                    score=score,
                    bm25_score=score,
                )
            )
        return results

    def _reciprocal_rank_fusion(
        self,
        vector_results: Sequence[RetrievalResult],
        bm25_results: Sequence[RetrievalResult],
    ) -> list[RetrievalResult]:
        """Fuse ranked lists with weighted Reciprocal Rank Fusion."""

        merged: dict[str, RetrievalResult] = {}
        scores: dict[str, float] = {}

        for rank, result in enumerate(vector_results, start=1):
            vector_result = result.with_scores(vector_score=result.vector_score or result.score)
            merged[result.id] = vector_result
            scores[result.id] = scores.get(result.id, 0.0) + self.vector_weight / (self.rrf_k + rank)

        for rank, result in enumerate(bm25_results, start=1):
            existing = merged.get(result.id)
            merged[result.id] = result if existing is None else existing.with_scores(bm25_score=result.bm25_score)
            scores[result.id] = scores.get(result.id, 0.0) + self.bm25_weight / (self.rrf_k + rank)

        return sorted(
            [result.with_scores(score=scores[result_id]) for result_id, result in merged.items()],
            key=lambda result: result.score,
            reverse=True,
        )

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokenize text for BM25 keyword search."""

        return re.findall(r"[\w#+.-]+", text.lower())
