import asyncio
import json
from pathlib import Path

from second_brain.repo_intel.rag import (
    IndexRepositoryInput,
    RetrieveInput,
    index_repository,
    retrieve,
)


def test_index_repository_persists_chunks_and_skips_ignored_dirs(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Demo\n\nUse asyncio workers for ingestion.\n",
        encoding="utf-8",
    )
    ignored = tmp_path / "node_modules"
    ignored.mkdir()
    (ignored / "package.js").write_text("asyncio should not be indexed", encoding="utf-8")
    binary = tmp_path / "image.png"
    binary.write_bytes(b"\x00\x01\x02")

    output = asyncio.run(index_repository(IndexRepositoryInput(repo_path=tmp_path)))

    assert output.files_indexed == 1
    assert output.chunks_indexed == 1
    assert output.index_path.exists()
    payload = json.loads(output.index_path.read_text(encoding="utf-8"))
    assert payload["chunks"][0]["path"] == "README.md"
    assert "node_modules" not in output.index_path.read_text(encoding="utf-8")


def test_retrieve_returns_lexical_matches(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("Project setup and onboarding guide.", encoding="utf-8")
    (tmp_path / "security.py").write_text(
        "def audit_secret_token():\n    return 'permission risk'\n",
        encoding="utf-8",
    )
    asyncio.run(index_repository(IndexRepositoryInput(repo_path=tmp_path)))

    output = asyncio.run(
        retrieve(
            RetrieveInput(repo_path=tmp_path, query="secret permission", mode="audit", top_k=2)
        )
    )

    assert output.results
    assert output.results[0].path == "security.py"
    assert output.results[0].score > 0
