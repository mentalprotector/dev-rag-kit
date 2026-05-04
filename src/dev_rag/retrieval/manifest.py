"""Load persisted chunks for sparse retrieval."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from dev_rag.ingestion.schemas import DocumentChunk

logger = logging.getLogger(__name__)


def load_chunk_manifest(path: str | Path, warn_missing: bool = True) -> list[DocumentChunk]:
    """Load ingested chunks from a JSONL manifest."""

    manifest_path = Path(path)
    if not manifest_path.exists():
        if warn_missing:
            logger.warning("Chunk manifest does not exist path=%s", manifest_path)
        return []

    chunks: list[DocumentChunk] = []
    with manifest_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                chunks.append(DocumentChunk.model_validate(json.loads(line)))
            except (json.JSONDecodeError, ValueError):
                logger.exception("Skipping invalid chunk manifest line path=%s line=%s", manifest_path, line_number)
    return chunks
