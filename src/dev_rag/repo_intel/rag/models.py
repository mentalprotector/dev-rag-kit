"""Pydantic models for local repository RAG."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RepoIntelMode = Literal["ask", "onboard", "audit"]


class RagChunk(BaseModel):
    """A persisted repository text chunk."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    text: str = Field(min_length=1)


class IndexRepositoryInput(BaseModel):
    """Input for building a local repository RAG index."""

    repo_path: Path
    chunk_size: int = Field(default=1200, ge=200)
    chunk_overlap: int = Field(default=120, ge=0)
    max_file_size_bytes: int = Field(default=1_000_000, ge=1)
    include_hidden_files: bool = False

    @field_validator("repo_path")
    @classmethod
    def repo_path_must_exist(cls, value: Path) -> Path:
        path = value.expanduser().resolve()
        if not path.exists() or not path.is_dir():
            raise ValueError(f"repo_path must be an existing directory: {value}")
        return path


class IndexRepositoryOutput(BaseModel):
    """Result of indexing a repository."""

    index_path: Path
    repo_path: Path
    files_indexed: int = Field(ge=0)
    files_skipped: int = Field(ge=0)
    chunks_indexed: int = Field(ge=0)


class RetrieveInput(BaseModel):
    """Input for local lexical retrieval."""

    repo_path: Path
    query: str = Field(min_length=1)
    top_k: int = Field(default=8, ge=1, le=100)
    mode: RepoIntelMode = "ask"

    @field_validator("repo_path")
    @classmethod
    def repo_path_must_exist(cls, value: Path) -> Path:
        path = value.expanduser().resolve()
        if not path.exists() or not path.is_dir():
            raise ValueError(f"repo_path must be an existing directory: {value}")
        return path


class RetrievedChunk(RagChunk):
    """A ranked repository chunk."""

    score: float = 0.0


class RetrieveOutput(BaseModel):
    """Result of local lexical retrieval."""

    index_path: Path
    query: str
    mode: RepoIntelMode
    results: list[RetrievedChunk]
