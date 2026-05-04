"""Pydantic schemas for ingestion documents and chunks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class Document(BaseModel):
    """Source document accepted by the ingestion pipeline."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DocumentChunk(BaseModel):
    """Chunk created from a source document."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    timestamp: datetime

    def qdrant_payload(self) -> dict[str, Any]:
        """Return a JSON-serializable payload for Qdrant."""

        return {
            "document_id": str(self.document_id),
            "content": self.content,
            "metadata": self.metadata,
            "source": self.source,
            "chunk_index": self.chunk_index,
            "timestamp": self.timestamp.isoformat(),
        }
