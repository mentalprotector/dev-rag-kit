"""Local deterministic repository indexer."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

from second_brain.repo_intel.rag.models import (
    IndexRepositoryInput,
    IndexRepositoryOutput,
    RagChunk,
)

INDEX_DIR = ".reposentinel/index"
INDEX_FILE = "index.json"
IGNORE_DIRS = {
    ".git",
    ".reposentinel/index",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "build",
    "dist",
    "node_modules",
}
TEXT_EXTENSIONS = {
    ".bat",
    ".cfg",
    ".cmd",
    ".conf",
    ".css",
    ".csv",
    ".env",
    ".gitignore",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsx",
    ".lock",
    ".md",
    ".mdx",
    ".py",
    ".rst",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}


async def index_repository(input_model: IndexRepositoryInput) -> IndexRepositoryOutput:
    """Build and persist a deterministic text chunk index for a repository."""

    return await asyncio.to_thread(_index_repository_sync, input_model)


def index_path(repo_path: Path) -> Path:
    """Return the persisted index path for a repository."""

    return repo_path / INDEX_DIR / INDEX_FILE


def _index_repository_sync(input_model: IndexRepositoryInput) -> IndexRepositoryOutput:
    repo_path = input_model.repo_path
    chunks: list[RagChunk] = []
    files_indexed = 0
    files_skipped = 0

    for path in _iter_candidate_files(repo_path, input_model.include_hidden_files):
        if _should_skip_file(path, repo_path, input_model.max_file_size_bytes):
            files_skipped += 1
            continue

        text = _read_text_file(path)
        if text is None or not text.strip():
            files_skipped += 1
            continue

        relative_path = path.relative_to(repo_path).as_posix()
        file_chunks = _chunk_text(
            relative_path=relative_path,
            text=text,
            chunk_size=input_model.chunk_size,
            chunk_overlap=input_model.chunk_overlap,
        )
        if file_chunks:
            chunks.extend(file_chunks)
            files_indexed += 1
        else:
            files_skipped += 1

    destination = index_path(repo_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "repo_path": str(repo_path),
        "chunks": [chunk.model_dump() for chunk in chunks],
    }
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(destination)

    return IndexRepositoryOutput(
        index_path=destination,
        repo_path=repo_path,
        files_indexed=files_indexed,
        files_skipped=files_skipped,
        chunks_indexed=len(chunks),
    )


def _iter_candidate_files(repo_path: Path, include_hidden_files: bool) -> list[Path]:
    paths: list[Path] = []
    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(repo_path).parts
        if _is_ignored(relative_parts):
            continue
        if not include_hidden_files and any(part.startswith(".") for part in relative_parts):
            continue
        paths.append(path)
    return sorted(paths, key=lambda item: item.relative_to(repo_path).as_posix())


def _is_ignored(relative_parts: tuple[str, ...]) -> bool:
    joined = "/".join(relative_parts)
    return any(part in IGNORE_DIRS for part in relative_parts) or joined.startswith(
        ".reposentinel/index/"
    )


def _should_skip_file(path: Path, repo_path: Path, max_file_size_bytes: int) -> bool:
    try:
        if path.stat().st_size > max_file_size_bytes:
            return True
    except OSError:
        return True

    relative = path.relative_to(repo_path)
    name = path.name.lower()
    suffix = path.suffix.lower()
    return (
        suffix not in TEXT_EXTENSIONS
        and name not in TEXT_EXTENSIONS
        and relative.name != "Dockerfile"
    )


def _read_text_file(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None
    if not _looks_like_text(text):
        return None
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _looks_like_text(text: str) -> bool:
    if not text:
        return False
    sample = text[:4096]
    control_chars = sum(1 for char in sample if ord(char) < 32 and char not in "\n\r\t\f\b")
    return control_chars / max(len(sample), 1) < 0.02


def _chunk_text(
    *,
    relative_path: str,
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[RagChunk]:
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    lines = text.splitlines()
    chunks: list[RagChunk] = []
    current: list[str] = []
    current_length = 0
    start_line = 1

    for line_number, line in enumerate(lines, start=1):
        line_with_newline = line if not current else f"\n{line}"
        candidate_length = current_length + len(line_with_newline)
        if current and candidate_length > chunk_size:
            chunk_text = "\n".join(current).strip()
            chunks.append(_build_chunk(relative_path, start_line, line_number - 1, chunk_text))
            current, current_length, start_line = _overlap_lines(
                current,
                chunk_overlap,
                line_number,
            )
        current.append(line)
        current_length = len("\n".join(current))

    if current:
        chunk_text = "\n".join(current).strip()
        if chunk_text:
            chunks.append(_build_chunk(relative_path, start_line, len(lines) or 1, chunk_text))

    return chunks


def _overlap_lines(
    lines: list[str],
    overlap_chars: int,
    next_line_number: int,
) -> tuple[list[str], int, int]:
    if overlap_chars <= 0:
        return [], 0, next_line_number

    selected: list[str] = []
    selected_length = 0
    for line in reversed(lines):
        added_length = len(line) + (1 if selected else 0)
        if selected and selected_length + added_length > overlap_chars:
            break
        selected.insert(0, line)
        selected_length += added_length
    start_line = next_line_number - len(selected)
    return selected, selected_length, max(start_line, 1)


def _build_chunk(relative_path: str, start_line: int, end_line: int, text: str) -> RagChunk:
    digest = hashlib.sha256(f"{relative_path}:{start_line}:{end_line}:{text}".encode("utf-8"))
    return RagChunk(
        id=digest.hexdigest()[:24],
        path=relative_path,
        start_line=start_line,
        end_line=max(end_line, start_line),
        text=text,
    )
