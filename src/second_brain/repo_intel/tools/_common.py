"""Shared helpers for local repository tools."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class ToolModel(BaseModel):
    """Base model with deterministic serialization defaults."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


def root_path(root: str | Path) -> Path:
    return Path(root).expanduser().resolve(strict=False)


def safe_path(root: str | Path, relative_path: str | Path = ".") -> Path:
    base = root_path(root)
    candidate = (base / relative_path).resolve(strict=False)
    if candidate != base and base not in candidate.parents:
        raise ValueError(f"path escapes root: {relative_path}")
    return candidate


def relative_to_root(root: Path, path: Path) -> str:
    return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()


def is_binary_bytes(data: bytes) -> bool:
    if not data:
        return False
    return b"\x00" in data[:4096]

