"""High-level ingestion pipeline."""

from __future__ import annotations

import logging
from pathlib import Path
import json

from dev_rag.config import AppConfig
from dev_rag.ingestion.chunker import RecursiveSemanticChunker
from dev_rag.ingestion.embeddings import EmbeddingService
from dev_rag.ingestion.qdrant_uploader import QdrantIngestionService
from dev_rag.ingestion.schemas import Document

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Load local text-like documents, chunk them, embed them, and upload to Qdrant."""

    def __init__(self, config: AppConfig) -> None:
        """Initialize pipeline services from app config."""

        self.chunker = RecursiveSemanticChunker(
            chunk_size=config.chunking.chunk_size,
            chunk_overlap=config.chunking.chunk_overlap,
        )
        self.manifest_path = Path(config.chunking.manifest_path)
        embedding_service = EmbeddingService(
            model_name=config.embedding.model_name,
            batch_size=config.embedding.batch_size,
        )
        self.uploader = QdrantIngestionService(
            qdrant_url=str(config.qdrant.url),
            collection_name=config.qdrant.collection,
            embedding_service=embedding_service,
        )

    def ingest_file(self, path: str | Path, metadata: dict[str, object] | None = None) -> int:
        """Ingest a Markdown or plain text file and return uploaded chunk count."""

        source_path = Path(path)
        try:
            content = source_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.exception("Failed to decode file as UTF-8 path=%s", source_path)
            raise
        except OSError:
            logger.exception("Failed to read file path=%s", source_path)
            raise

        document = Document(
            content=content,
            metadata={
                "file_name": source_path.name,
                "extension": source_path.suffix.lower(),
                **(metadata or {}),
            },
            source=str(source_path),
        )
        chunks = self.chunker.chunk_document(document)
        uploaded = self.uploader.upload_chunks(chunks)
        self._append_manifest(chunks)
        return uploaded

    def _append_manifest(self, chunks: list[object]) -> None:
        """Persist chunks locally for sparse BM25 retrieval between CLI runs."""

        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with self.manifest_path.open("a", encoding="utf-8") as file:
            for chunk in chunks:
                file.write(json.dumps(chunk.model_dump(mode="json"), ensure_ascii=False) + "\n")
