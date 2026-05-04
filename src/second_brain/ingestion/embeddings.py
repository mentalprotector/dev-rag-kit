"""Embedding generation service."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate dense embeddings with a sentence-transformers model."""

    def __init__(self, model_name: str, batch_size: int = 32) -> None:
        """Initialize the embedding model."""

        self.model_name = model_name
        self.batch_size = batch_size
        logger.info("Loading embedding model=%s", model_name)
        self._model = SentenceTransformer(model_name)

    @property
    def dimension(self) -> int:
        """Return embedding vector dimension."""

        return int(self._model.get_sentence_embedding_dimension())

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a sequence of texts as normalized float vectors."""

        if not texts:
            return []
        try:
            vectors = self._model.encode(
                list(texts),
                batch_size=self.batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception:
            logger.exception("Embedding generation failed")
            raise
        return vectors.astype("float32").tolist()
