"""Semantic-aware recursive chunking for Markdown and plain text."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from second_brain.ingestion.schemas import Document, DocumentChunk

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecursiveSemanticChunker:
    """Split Markdown or plain text while preserving headers and fenced code blocks."""

    chunk_size: int = 1200
    chunk_overlap: int = 180

    def __post_init__(self) -> None:
        """Validate chunking parameters."""

        if self.chunk_size < 200:
            raise ValueError("chunk_size must be at least 200 characters")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")

    def chunk_document(self, document: Document) -> list[DocumentChunk]:
        """Split a document into semantic chunks."""

        sections = self._split_markdown_sections(document.content)
        raw_chunks: list[str] = []
        for section in sections:
            raw_chunks.extend(self._split_recursively(section.strip()))

        chunks = [
            DocumentChunk(
                document_id=document.id,
                content=content,
                metadata={**document.metadata, "char_length": len(content)},
                source=document.source,
                chunk_index=index,
                timestamp=document.timestamp,
            )
            for index, content in enumerate(raw_chunks)
            if content.strip()
        ]
        logger.info("Chunked document source=%s chunks=%s", document.source, len(chunks))
        return chunks

    def _split_markdown_sections(self, text: str) -> list[str]:
        """Split Markdown by headers outside fenced code blocks."""

        sections: list[str] = []
        current: list[str] = []
        in_code_block = False

        for line in text.splitlines():
            if line.lstrip().startswith("```"):
                in_code_block = not in_code_block
            is_header = not in_code_block and re.match(r"^#{1,6}\s+\S", line) is not None
            if is_header and current:
                sections.append("\n".join(current))
                current = [line]
            else:
                current.append(line)

        if current:
            sections.append("\n".join(current))
        return sections or [text]

    def _split_recursively(self, text: str) -> list[str]:
        """Split text with increasingly granular separators and overlap."""

        if len(text) <= self.chunk_size:
            return [text] if text else []

        units = self._split_preserving_code_blocks(text)
        chunks: list[str] = []
        current = ""

        for unit in units:
            candidate = f"{current}{unit}" if current else unit
            if len(candidate) <= self.chunk_size:
                current = candidate
                continue

            if current:
                chunks.append(current.strip())
                current = self._overlap_suffix(current) + unit
            else:
                chunks.extend(self._hard_split(unit))
                current = ""

            while len(current) > self.chunk_size:
                chunks.append(current[: self.chunk_size].strip())
                current = self._overlap_suffix(current[: self.chunk_size]) + current[self.chunk_size :]

        if current.strip():
            chunks.append(current.strip())
        return chunks

    def _split_preserving_code_blocks(self, text: str) -> list[str]:
        """Create split units while keeping fenced code blocks as indivisible as possible."""

        units: list[str] = []
        buffer: list[str] = []
        in_code_block = False

        for line in text.splitlines(keepends=True):
            if line.lstrip().startswith("```"):
                in_code_block = not in_code_block
            buffer.append(line)
            if not in_code_block and (line.strip() == "" or re.match(r"^#{1,6}\s+\S", line)):
                units.append("".join(buffer))
                buffer = []

        if buffer:
            units.append("".join(buffer))

        paragraph_units: list[str] = []
        for unit in units:
            if len(unit) <= self.chunk_size:
                paragraph_units.append(unit)
            else:
                paragraph_units.extend(self._split_by_sentences(unit))
        return paragraph_units

    def _split_by_sentences(self, text: str) -> list[str]:
        """Split oversized text by sentence-like boundaries."""

        pieces = re.split(r"(?<=[.!?])\s+", text)
        return [f"{piece} " for piece in pieces if piece.strip()]

    def _hard_split(self, text: str) -> list[str]:
        """Split text that has no usable semantic boundaries."""

        chunks: list[str] = []
        start = 0
        step = self.chunk_size - self.chunk_overlap
        while start < len(text):
            chunks.append(text[start : start + self.chunk_size].strip())
            start += step
        return [chunk for chunk in chunks if chunk]

    def _overlap_suffix(self, text: str) -> str:
        """Return a whitespace-aligned suffix used as chunk overlap."""

        suffix = text[-self.chunk_overlap :] if self.chunk_overlap else ""
        first_space = suffix.find(" ")
        if first_space > 0:
            return suffix[first_space + 1 :]
        return suffix
