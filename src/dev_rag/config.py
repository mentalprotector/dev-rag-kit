"""Configuration loading for Dev RAG Kit."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, HttpUrl


_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::([^}]*))?\}")


class QdrantConfig(BaseModel):
    """Qdrant connection settings."""

    url: HttpUrl = Field(default="http://localhost:6333")
    collection: str = Field(default="dev_rag_docs", min_length=1)


class EmbeddingConfig(BaseModel):
    """Embedding model settings."""

    model_name: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", min_length=1)
    batch_size: int = Field(default=32, ge=1)


class ChunkingConfig(BaseModel):
    """Text chunking settings."""

    chunk_size: int = Field(default=1200, ge=200)
    chunk_overlap: int = Field(default=180, ge=0)
    manifest_path: str = Field(default="data/chunks.jsonl", min_length=1)


class LLMConfig(BaseModel):
    """OpenAI-compatible LLM API settings."""

    api_base_url: HttpUrl = Field(default="http://localhost:1234/v1")
    model_name: str = Field(min_length=1)
    timeout_seconds: float = Field(default=60.0, gt=0)


class AppConfig(BaseModel):
    """Application configuration."""

    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)


def _expand_env(value: Any) -> Any:
    """Recursively expand ${VAR:default} placeholders in YAML-loaded values."""

    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if not isinstance(value, str):
        return value

    def replace(match: re.Match[str]) -> str:
        name, default = match.group(1), match.group(2)
        return os.getenv(name, default or "")

    expanded = _ENV_PATTERN.sub(replace, value)
    if expanded.isdigit():
        return int(expanded)
    return expanded


def load_config(path: str | Path = "config/default.yaml") -> AppConfig:
    """Load application configuration from YAML and environment variables."""

    load_dotenv()
    config_path = Path(path)
    if not config_path.exists():
        return AppConfig()

    with config_path.open("r", encoding="utf-8") as file:
        raw_config = yaml.safe_load(file) or {}
    return AppConfig.model_validate(_expand_env(raw_config))
