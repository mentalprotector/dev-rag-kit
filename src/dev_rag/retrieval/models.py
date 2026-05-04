"""Pydantic models for retrieval data flow."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RetrievalResult(BaseModel):
    """Ranked chunk returned by retrieval or reranking stages."""

    model_config = ConfigDict(frozen=True)

    id: str
    content: str = Field(min_length=1)
    source: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    document_id: UUID | None = None
    chunk_index: int | None = Field(default=None, ge=0)
    timestamp: datetime | None = None
    score: float = 0.0
    vector_score: float | None = None
    bm25_score: float | None = None
    rerank_score: float | None = None

    @classmethod
    def from_qdrant_payload(
        cls,
        point_id: str,
        payload: dict[str, Any],
        score: float,
    ) -> "RetrievalResult":
        """Build a retrieval result from a Qdrant point payload."""

        return cls(
            id=point_id,
            content=str(payload.get("content", "")),
            source=str(payload.get("source", "unknown")),
            metadata=dict(payload.get("metadata") or {}),
            document_id=payload.get("document_id"),
            chunk_index=payload.get("chunk_index"),
            timestamp=payload.get("timestamp"),
            score=score,
            vector_score=score,
        )

    def with_scores(
        self,
        *,
        score: float | None = None,
        vector_score: float | None = None,
        bm25_score: float | None = None,
        rerank_score: float | None = None,
    ) -> "RetrievalResult":
        """Return a copy with updated stage scores."""

        return self.model_copy(
            update={
                "score": self.score if score is None else score,
                "vector_score": self.vector_score if vector_score is None else vector_score,
                "bm25_score": self.bm25_score if bm25_score is None else bm25_score,
                "rerank_score": self.rerank_score if rerank_score is None else rerank_score,
            }
        )
