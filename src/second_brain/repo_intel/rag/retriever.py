"""Local lexical retrieval over persisted repository chunks."""

from __future__ import annotations

import asyncio
import json
import math
import re
from collections import Counter
from pathlib import Path

from second_brain.repo_intel.rag.indexer import index_path
from second_brain.repo_intel.rag.models import RetrieveInput, RetrieveOutput, RetrievedChunk

TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
MODE_TERMS = {
    "ask": ("readme", "setup", "install", "run", "start", "quickstart", "usage", "cli", "project"),
    "onboard": ("readme", "overview", "architecture", "setup", "quickstart", "config", "cli"),
    "audit": ("security", "auth", "permission", "secret", "risk", "test", "error", "todo"),
}


async def retrieve(input_model: RetrieveInput) -> RetrieveOutput:
    """Retrieve relevant repository chunks from the local persisted index."""

    return await asyncio.to_thread(_retrieve_sync, input_model)


def _retrieve_sync(input_model: RetrieveInput) -> RetrieveOutput:
    destination = index_path(input_model.repo_path)
    chunks = _load_chunks(destination)
    query_tokens = _tokens(input_model.query) + list(MODE_TERMS[input_model.mode])
    if not query_tokens or not chunks:
        return RetrieveOutput(
            index_path=destination,
            query=input_model.query,
            mode=input_model.mode,
            results=[],
        )

    scored = _rank_chunks(chunks, query_tokens, input_model.mode)
    results = [
        RetrievedChunk(**chunk.model_dump(exclude={"score"}), score=score)
        for chunk, score in scored[: input_model.top_k]
        if score > 0
    ]
    return RetrieveOutput(
        index_path=destination,
        query=input_model.query,
        mode=input_model.mode,
        results=results,
    )


def _load_chunks(destination: Path) -> list[RetrievedChunk]:
    if not destination.exists():
        raise FileNotFoundError(f"Repository index not found: {destination}")
    data = json.loads(destination.read_text(encoding="utf-8"))
    return [RetrievedChunk(**chunk, score=0.0) for chunk in data.get("chunks", [])]


def _rank_chunks(
    chunks: list[RetrievedChunk],
    query_tokens: list[str],
    mode: str,
) -> list[tuple[RetrievedChunk, float]]:
    tokenized = [_tokens(chunk.text) + _tokens(chunk.path) for chunk in chunks]
    try:
        from rank_bm25 import BM25Okapi  # type: ignore[import-not-found]

        bm25 = BM25Okapi(tokenized)
        scores = bm25.get_scores(query_tokens)
        pairs = [
            (chunk, float(score) + _token_overlap_score(query_tokens, document_tokens) + _path_priority(chunk.path, mode))
            for chunk, score, document_tokens in zip(chunks, scores, tokenized, strict=True)
        ]
    except Exception:
        pairs = [
            (chunk, _token_overlap_score(query_tokens, document_tokens) + _path_priority(chunk.path, mode))
            for chunk, document_tokens in zip(chunks, tokenized, strict=True)
        ]

    return sorted(
        pairs,
        key=lambda item: (
            -item[1],
            -_path_mode_boost(item[0].path, query_tokens),
            item[0].start_line,
            item[0].path,
        ),
    )


def _tokens(text: str) -> list[str]:
    normalized = text.replace("_", " ").replace("-", " ").replace(".", " ")
    return [match.group(0).lower() for match in TOKEN_RE.finditer(normalized)]


def _token_overlap_score(query_tokens: list[str], document_tokens: list[str]) -> float:
    query_counts = Counter(query_tokens)
    document_counts = Counter(document_tokens)
    overlap = sum(min(count, document_counts[token]) for token, count in query_counts.items())
    if overlap == 0:
        return 0.0
    length_penalty = math.sqrt(max(len(document_tokens), 1))
    return overlap / length_penalty


def _path_mode_boost(path: str, query_tokens: list[str]) -> float:
    path_tokens = set(_tokens(path))
    query_set = set(query_tokens)
    return float(len(path_tokens & query_set))


def _path_priority(path: str, mode: str) -> float:
    if mode == "audit":
        return 0.0
    lowered = path.lower()
    if lowered in {"readme.md", "pyproject.toml", "package.json"}:
        return 100.0
    if lowered.endswith(("/readme.md", "/pyproject.toml", "/package.json")):
        return 80.0
    if "/tests/" in f"/{lowered}":
        return -0.5
    return 0.0
