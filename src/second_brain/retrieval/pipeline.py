"""High-level retrieval pipeline orchestration."""

from __future__ import annotations

from typing import Protocol

from second_brain.retrieval.hybrid_search import HybridSearchEngine
from second_brain.retrieval.models import RetrievalResult


class RerankerBackend(Protocol):
    """Protocol for reranking implementations."""

    def rerank(
        self,
        query: str,
        documents: list[RetrievalResult],
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        """Return reranked retrieval results."""


class RetrievalPipeline:
    """Run query retrieval from hybrid search through reranking to final context."""

    def __init__(self, hybrid_search: HybridSearchEngine, reranker: RerankerBackend) -> None:
        """Initialize pipeline stages."""

        self.hybrid_search = hybrid_search
        self.reranker = reranker

    def retrieve(
        self,
        query: str,
        hybrid_limit: int = 20,
        final_limit: int = 5,
    ) -> list[RetrievalResult]:
        """Return final reranked retrieval results for a query."""

        candidates = self.hybrid_search.search(query=query, limit=hybrid_limit)
        return self.reranker.rerank(query=query, documents=candidates, top_k=final_limit)

    def build_context(self, results: list[RetrievalResult]) -> str:
        """Build a compact context block from final retrieval results."""

        return "\n\n".join(
            f"[source={result.source} chunk={result.chunk_index}]\n{result.content}" for result in results
        )
