import json
from pathlib import Path

from dev_rag.repo_intel.reports import (
    ProjectProfile,
    SecurityFinding,
    render_project_brief,
    render_security_audit,
    write_reports,
)


def test_render_project_brief_includes_onboarding_sections() -> None:
    profile = ProjectProfile(
        name="Example",
        summary="Python service for repository intelligence.",
        languages=["Python"],
        frameworks=["Pydantic"],
        package_managers=["pip"],
        entrypoints=["src/example/app.py"],
        test_commands=["pytest"],
        build_commands=["python -m build"],
        manifests=["pyproject.toml"],
        open_questions=["Which deployment target is canonical?"],
        evidence=["README.md describes the service."],
    )

    markdown = render_project_brief(
        profile,
        scans={"commands": ["pytest -q"], "observations": ["Found pyproject.toml"]},
        retrieval_context=[{"source": "README.md", "score": 0.9, "content": "Repository overview"}],
    )

    assert "# Repository Onboarding Brief: Example" in markdown
    assert "## Commands" in markdown
    assert "- `pytest`" in markdown
    assert "## Manifests" in markdown
    assert "- pyproject.toml" in markdown
    assert "## Evidence" in markdown
    assert "README.md (score: 0.9): Repository overview" in markdown
    assert "## Open Questions" in markdown


def test_render_security_audit_includes_summary_findings_and_scan_context() -> None:
    findings = [
        SecurityFinding(
            id="secret-1",
            title="Potential secret in env file",
            severity="high",
            description="A local environment file may contain credentials.",
            evidence=[".env contains API_KEY-like variable."],
            files=[".env"],
            commands=["Select-String -Path .env -Pattern API_KEY"],
            recommendation="Move secrets to a managed secret store.",
            open_questions=["Is .env excluded from distribution artifacts?"],
        )
    ]

    markdown = render_security_audit(
        findings,
        scans={"manifests": ["pyproject.toml"], "commands": ["git status --short"]},
    )

    assert "- **High:** 1" in markdown
    assert "### [HIGH] Potential secret in env file" in markdown
    assert "- **Files:** `.env`" in markdown
    assert "- `Select-String -Path .env -Pattern API_KEY`" in markdown
    assert "## Manifests" in markdown
    assert "- pyproject.toml" in markdown
    assert "Is .env excluded from distribution artifacts?" in markdown


def test_write_reports_creates_repo_check_artifacts(tmp_path: Path) -> None:
    finding = SecurityFinding(id="f1", title="Informational note")

    paths = write_reports(
        tmp_path,
        "# Brief\n",
        "# Audit\n",
        [finding],
    )

    assert paths["project_brief"].read_text(encoding="utf-8") == "# Brief\n"
    assert paths["security_audit"].read_text(encoding="utf-8") == "# Audit\n"
    findings_payload = json.loads(paths["findings_json"].read_text(encoding="utf-8"))
    assert findings_payload[0]["id"] == "f1"
    assert paths["findings_json"].parent == tmp_path / ".repo-check"
