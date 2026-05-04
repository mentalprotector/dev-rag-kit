"""Deterministic repository file scanner."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from dev_rag.repo_intel.tools._common import ToolModel, relative_to_root, root_path

DEFAULT_IGNORES = {
    ".git",
    "node_modules",
    ".venv",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".repo-check/index",
}


class ScannedPath(ToolModel):
    path: str
    kind: str
    size_bytes: int | None = None


class RepoScanRequest(ToolModel):
    root: str
    max_files: int = Field(default=1000, ge=1)
    ignores: set[str] = Field(default_factory=lambda: set(DEFAULT_IGNORES))
    include_dirs: bool = True


class RepoScanResult(ToolModel):
    root: str
    files: list[ScannedPath] = Field(default_factory=list)
    dirs: list[ScannedPath] = Field(default_factory=list)
    truncated: bool = False
    ignored: list[str] = Field(default_factory=list)


def _is_ignored(rel: str, ignores: set[str]) -> bool:
    parts = rel.split("/")
    return any(pattern == rel or pattern in parts for pattern in ignores)


async def scan_repo(request: RepoScanRequest) -> RepoScanResult:
    root = root_path(request.root)
    files: list[ScannedPath] = []
    dirs: list[ScannedPath] = []
    ignored: set[str] = set()

    def walk(directory: Path) -> None:
        nonlocal files
        if len(files) >= request.max_files:
            return
        for child in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
            rel = relative_to_root(root, child)
            if _is_ignored(rel, request.ignores):
                ignored.add(rel)
                continue
            if child.is_dir():
                if request.include_dirs:
                    dirs.append(ScannedPath(path=rel, kind="dir"))
                walk(child)
            elif child.is_file():
                if len(files) >= request.max_files:
                    return
                files.append(ScannedPath(path=rel, kind="file", size_bytes=child.stat().st_size))

    if root.exists():
        walk(root)
    return RepoScanResult(
        root=str(root),
        files=files,
        dirs=dirs,
        truncated=len(files) >= request.max_files,
        ignored=sorted(ignored),
    )

