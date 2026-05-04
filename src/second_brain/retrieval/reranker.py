"""Cross-encoder reranking for retrieval candidates."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sentence_transformers import CrossEncoder

from second_brain.retrieval.models import RetrievalResult

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Rerank retrieved chunks with a sentence-transformers CrossEncoder."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        """Load the cross-encoder model."""

        self.model_name = model_name
        logger.info("Loading reranker model=%s", model_name)
        self._model = CrossEncoder(model_name)

    def rerank(
        self,
        query: str,
        documents: Sequence[RetrievalResult],
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        """Score query-document pairs and return the best chunks."""

        if not query.strip():
            raise ValueError("query must not be empty")
        if not documents:
            return []

        pairs = [(query, document.content) for document in documents]
        try:
            scores = self._model.predict(pairs)
        except Exception:
            logger.exception("Cross-encoder reranking failed model=%s", self.model_name)
            raise

        reranked = sorted(
            (
                document.with_scores(score=float(score), rerank_score=float(score))
                for document, score in zip(documents, scores, strict=True)
            ),
            key=lambda result: result.rerank_score if result.rerank_score is not None else result.score,
            reverse=True,
        )
        return reranked[:top_k] if top_k is not None else reranked
