"""Qdrant upload service for ingested chunks."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from qdrant_client import QdrantClient
from qdrant_client.http import exceptions as qdrant_exceptions
from qdrant_client.models import Distance, PointStruct, VectorParams

from dev_rag.ingestion.embeddings import EmbeddingService
from dev_rag.ingestion.schemas import DocumentChunk

logger = logging.getLogger(__name__)


class QdrantIngestionService:
    """Create Qdrant collections and upload embedded chunks."""

    def __init__(
        self,
        qdrant_url: str,
        collection_name: str,
        embedding_service: EmbeddingService,
        timeout_seconds: float = 30.0,
    ) -> None:
        """Initialize the Qdrant ingestion service."""

        self.collection_name = collection_name
        self.embedding_service = embedding_service
        self.client = QdrantClient(url=qdrant_url, timeout=timeout_seconds)

    def ensure_collection(self) -> None:
        """Create the collection if it does not exist."""

        try:
            if self.client.collection_exists(self.collection_name):
                return
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_service.dimension,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection=%s", self.collection_name)
        except qdrant_exceptions.UnexpectedResponse:
            logger.exception("Qdrant rejected collection setup collection=%s", self.collection_name)
            raise
        except Exception:
            logger.exception("Qdrant collection setup failed collection=%s", self.collection_name)
            raise

    def upload_chunks(self, chunks: Sequence[DocumentChunk], batch_size: int = 64) -> int:
        """Embed and upload chunks to Qdrant, returning the number of uploaded points."""

        if not chunks:
            return 0

        self.ensure_collection()
        uploaded = 0
        for start in range(0, len(chunks), batch_size):
            batch = list(chunks[start : start + batch_size])
            vectors = self.embedding_service.embed_texts([chunk.content for chunk in batch])
            points = [
                PointStruct(
                    id=str(chunk.id),
                    vector=vector,
                    payload=chunk.qdrant_payload(),
                )
                for chunk, vector in zip(batch, vectors, strict=True)
            ]
            try:
                self.client.upsert(collection_name=self.collection_name, points=points)
            except qdrant_exceptions.UnexpectedResponse:
                logger.exception("Qdrant rejected upsert collection=%s", self.collection_name)
                raise
            except Exception:
                logger.exception("Qdrant upsert failed collection=%s", self.collection_name)
                raise
            uploaded += len(points)
            logger.info("Uploaded Qdrant batch collection=%s size=%s", self.collection_name, len(points))

        return uploaded
