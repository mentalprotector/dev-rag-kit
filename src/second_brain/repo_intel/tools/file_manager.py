"""Safe async file management within a repository root."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from second_brain.repo_intel.tools._common import ToolModel, is_binary_bytes, relative_to_root, safe_path


class ReadFileRequest(ToolModel):
    root: str
    path: str
    encoding: str = "utf-8"
    max_bytes: int = Field(default=1_000_000, ge=1)


class WriteFileRequest(ToolModel):
    root: str
    path: str
    content: str
    encoding: str = "utf-8"
    create_parents: bool = True
    overwrite: bool = True


class ListFilesRequest(ToolModel):
    root: str
    path: str = "."
    recursive: bool = False
    include_dirs: bool = True
    max_entries: int = Field(default=500, ge=1)


class DeleteFileRequest(ToolModel):
    root: str
    path: str
    missing_ok: bool = False


class FileEntry(ToolModel):
    path: str
    kind: str
    size_bytes: int | None = None


class FileManagerResult(ToolModel):
    ok: bool
    path: str | None = None
    content: str | None = None
    bytes_read: int | None = None
    bytes_written: int | None = None
    entries: list[FileEntry] = Field(default_factory=list)
    error: str | None = None


async def read_file(request: ReadFileRequest) -> FileManagerResult:
    try:
        path = safe_path(request.root, request.path)
        data = path.read_bytes()[: request.max_bytes]
        if is_binary_bytes(data):
            return FileManagerResult(ok=False, path=request.path, error="binary file is not supported")
        return FileManagerResult(
            ok=True,
            path=relative_to_root(Path(request.root), path),
            content=data.decode(request.encoding, errors="replace"),
            bytes_read=len(data),
        )
    except Exception as exc:
        return FileManagerResult(ok=False, path=request.path, error=str(exc))


async def write_file(request: WriteFileRequest) -> FileManagerResult:
    try:
        path = safe_path(request.root, request.path)
        if path.exists() and not request.overwrite:
            return FileManagerResult(ok=False, path=request.path, error="file already exists")
        if request.create_parents:
            path.parent.mkdir(parents=True, exist_ok=True)
        data = request.content.encode(request.encoding)
        path.write_bytes(data)
        return FileManagerResult(
            ok=True,
            path=relative_to_root(Path(request.root), path),
            bytes_written=len(data),
        )
    except Exception as exc:
        return FileManagerResult(ok=False, path=request.path, error=str(exc))


async def list_files(request: ListFilesRequest) -> FileManagerResult:
    try:
        root = Path(request.root).resolve(strict=False)
        base = safe_path(root, request.path)
        iterator = base.rglob("*") if request.recursive else base.iterdir()
        entries: list[FileEntry] = []
        for item in sorted(iterator, key=lambda p: p.as_posix()):
            if len(entries) >= request.max_entries:
                break
            if item.is_dir():
                if request.include_dirs:
                    entries.append(FileEntry(path=relative_to_root(root, item), kind="dir"))
            else:
                entries.append(
                    FileEntry(path=relative_to_root(root, item), kind="file", size_bytes=item.stat().st_size)
                )
        return FileManagerResult(ok=True, path=relative_to_root(root, base), entries=entries)
    except Exception as exc:
        return FileManagerResult(ok=False, path=request.path, error=str(exc))


async def delete_file(request: DeleteFileRequest) -> FileManagerResult:
    try:
        path = safe_path(request.root, request.path)
        if not path.exists():
            if request.missing_ok:
                return FileManagerResult(ok=True, path=request.path)
            return FileManagerResult(ok=False, path=request.path, error="path does not exist")
        if path.is_dir():
            return FileManagerResult(ok=False, path=request.path, error="refusing to delete directory")
        path.unlink()
        return FileManagerResult(ok=True, path=request.path)
    except Exception as exc:
        return FileManagerResult(ok=False, path=request.path, error=str(exc))

