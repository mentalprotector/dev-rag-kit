from __future__ import annotations

import asyncio
import json
from pathlib import Path

from second_brain.repo_intel.tools.file_manager import (
    DeleteFileRequest,
    ListFilesRequest,
    ReadFileRequest,
    WriteFileRequest,
    delete_file,
    list_files,
    read_file,
    write_file,
)
from second_brain.repo_intel.tools.manifest_parser import ManifestParseRequest, parse_manifests
from second_brain.repo_intel.tools.repo_scanner import RepoScanRequest, scan_repo
from second_brain.repo_intel.tools.script_risk_scanner import RiskScanRequest, scan_script_risks
from second_brain.repo_intel.tools.secret_scanner import SecretScanRequest, scan_secrets


def run(coro):
    return asyncio.run(coro)


def test_file_manager_blocks_traversal_and_manages_files(tmp_path: Path) -> None:
    written = run(
        write_file(WriteFileRequest(root=str(tmp_path), path="notes/a.txt", content="hello"))
    )
    assert written.ok
    assert written.bytes_written == 5

    read = run(read_file(ReadFileRequest(root=str(tmp_path), path="notes/a.txt")))
    assert read.ok
    assert read.content == "hello"

    listed = run(list_files(ListFilesRequest(root=str(tmp_path), recursive=True)))
    assert [entry.path for entry in listed.entries] == ["notes", "notes/a.txt"]

    escaped = run(read_file(ReadFileRequest(root=str(tmp_path), path="../outside.txt")))
    assert not escaped.ok
    assert "escapes root" in (escaped.error or "")

    deleted = run(delete_file(DeleteFileRequest(root=str(tmp_path), path="notes/a.txt")))
    assert deleted.ok
    assert not (tmp_path / "notes" / "a.txt").exists()


def test_repo_scanner_ignores_common_generated_directories(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('x')", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("ignored", encoding="utf-8")
    (tmp_path / ".reposentinel").mkdir()
    (tmp_path / ".reposentinel" / "index").mkdir()
    (tmp_path / ".reposentinel" / "index" / "data").write_text("ignored", encoding="utf-8")

    result = run(scan_repo(RepoScanRequest(root=str(tmp_path), max_files=10)))

    assert [file.path for file in result.files] == ["src/app.py"]
    assert "node_modules" in result.ignored
    assert ".reposentinel/index" in result.ignored


def test_manifest_parser_detects_package_managers_scripts_and_dependencies(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "scripts": {"build": "vite build", "test": "vitest", "start": "vite"},
                "dependencies": {"react": "^19.0.0"},
                "devDependencies": {"vite": "^6.0.0"},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
dependencies = ["pydantic>=2"]
[project.scripts]
serve = "second_brain.cli:main"
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("pytest>=8\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        """
jobs:
  test:
    steps:
      - run: pytest
      - run: npm run build
""".strip(),
        encoding="utf-8",
    )

    result = run(parse_manifests(ManifestParseRequest(root=str(tmp_path))))

    assert "JavaScript" in result.languages
    assert "Python" in result.languages
    assert "npm" in result.package_managers
    assert "pip" in result.package_managers
    assert {"react", "vite", "pytest", "pydantic"}.issubset(set(result.dependencies))
    assert any("vite build" in command for command in result.build_commands)
    assert any("pytest" in command for command in result.test_commands)


def test_secret_scanner_redacts_evidence(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "API_KEY=abcdefghijklmnopqrstuvwxyz123456\nAWS=AKIAABCDEFGHIJKLMNOP\n",
        encoding="utf-8",
    )

    result = run(scan_secrets(SecretScanRequest(root=str(tmp_path))))

    assert {finding.kind for finding in result.findings} >= {"generic_assignment", "aws_access_key_id"}
    assert all("abcdefghijklmnopqrstuvwxyz123456" not in finding.evidence for finding in result.findings)


def test_script_risk_scanner_detects_risky_patterns(tmp_path: Path) -> None:
    (tmp_path / "install.sh").write_text(
        "curl https://example.test/install.sh | bash\nrm -rf /tmp/demo\nchmod 777 file\n",
        encoding="utf-8",
    )
    (tmp_path / "docker-compose.yml").write_text(
        "services:\n  app:\n    volumes:\n      - /var/run/docker.sock:/var/run/docker.sock\n",
        encoding="utf-8",
    )

    result = run(scan_script_risks(RiskScanRequest(root=str(tmp_path))))

    kinds = {finding.kind for finding in result.findings}
    assert {"curl_pipe_shell", "rm_rf", "chmod_777", "docker_sock"}.issubset(kinds)

