"""Qdrant vector retrieval wrapper."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from qdrant_client import QdrantClient
from qdrant_client.http import exceptions as qdrant_exceptions

from dev_rag.retrieval.models import RetrievalResult

logger = logging.getLogger(__name__)


class QdrantClientWrapper:
    """Small Qdrant adapter for dense vector search."""

    def __init__(self, qdrant_url: str, collection_name: str, timeout_seconds: float = 30.0) -> None:
        """Initialize Qdrant client settings."""

        self.collection_name = collection_name
        self.client = QdrantClient(url=qdrant_url, timeout=timeout_seconds)

    def search(self, query_vector: Sequence[float], limit: int = 10) -> list[RetrievalResult]:
        """Return nearest chunks from Qdrant with payload metadata."""

        if limit < 1:
            raise ValueError("limit must be at least 1")
        try:
            points = self._query_points(query_vector=query_vector, limit=limit)
        except qdrant_exceptions.UnexpectedResponse:
            logger.exception("Qdrant search rejected collection=%s", self.collection_name)
            raise
        except Exception:
            logger.exception("Qdrant search failed collection=%s", self.collection_name)
            raise

        results: list[RetrievalResult] = []
        for point in points:
            payload = dict(point.payload or {})
            if not payload.get("content"):
                logger.warning("Skipping Qdrant point without content id=%s", point.id)
                continue
            results.append(
                RetrievalResult.from_qdrant_payload(
                    point_id=str(point.id),
                    payload=payload,
                    score=float(point.score),
                )
            )
        return results

    def _query_points(self, query_vector: Sequence[float], limit: int) -> list[object]:
        """Run vector search across supported qdrant-client versions."""

        if hasattr(self.client, "query_points"):
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=list(query_vector),
                limit=limit,
                with_payload=True,
            )
            return list(response.points)

        return list(
            self.client.search(
                collection_name=self.collection_name,
                query_vector=list(query_vector),
                limit=limit,
                with_payload=True,
            )
        )
