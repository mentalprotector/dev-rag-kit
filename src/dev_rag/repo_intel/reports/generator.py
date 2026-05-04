"""Report rendering for repository onboarding and local security audit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["critical", "high", "medium", "low", "info"]
SEVERITY_ORDER: tuple[Severity, ...] = ("critical", "high", "medium", "low", "info")


class ProjectProfile(BaseModel):
    """Concise repository profile used to render an onboarding brief."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(default="Unknown project")
    summary: str = Field(default="No project summary was provided.")
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    entrypoints: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    build_commands: list[str] = Field(default_factory=list)
    run_commands: list[str] = Field(default_factory=list)
    manifests: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class SecurityFinding(BaseModel):
    """Local security audit finding with enough context for markdown and JSON."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default="finding")
    title: str
    severity: Severity = "info"
    description: str = ""
    evidence: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    commands: list[str] = Field(default_factory=list)
    recommendation: str = ""
    open_questions: list[str] = Field(default_factory=list)


def render_project_brief(
    profile: ProjectProfile | dict[str, Any],
    scans: dict[str, Any] | None = None,
    retrieval_context: list[Any] | dict[str, Any] | str | None = None,
) -> str:
    """Render a repository onboarding brief as markdown."""

    project = _coerce_project_profile(profile)
    scan_data = scans or {}
    lines = [
        f"# Repository Onboarding Brief: {project.name}",
        "",
        "## Summary",
        project.summary,
        "",
        "## Project Profile",
        _bullet_line("Languages", project.languages),
        _bullet_line("Frameworks", project.frameworks),
        _bullet_line("Package managers", project.package_managers),
        _bullet_line("Entrypoints", project.entrypoints),
        "",
        "## Commands",
        *_command_block("Run", project.run_commands),
        *_command_block("Build", project.build_commands),
        *_command_block("Test", project.test_commands),
        "",
        "## Manifests",
        *_bullet_list(project.manifests or _extract_named_items(scan_data, ("manifests", "manifest_files"))),
        "",
        "## Evidence",
        *_bullet_list(project.evidence),
        *_scan_evidence(scan_data),
        "",
        "## Retrieval Context",
        *_retrieval_context_lines(retrieval_context),
        "",
        "## Open Questions",
        *_bullet_list(project.open_questions),
        "",
    ]
    return _clean_markdown(lines)


def render_security_audit(
    findings: list[SecurityFinding | dict[str, Any]],
    scans: dict[str, Any] | None = None,
) -> str:
    """Render local security audit findings as markdown."""

    normalized = [_coerce_security_finding(finding) for finding in findings]
    scan_data = scans or {}
    lines = [
        "# Local Security Audit",
        "",
        "## Severity Summary",
        *_severity_summary(normalized),
        "",
        "## Findings",
    ]
    if normalized:
        for finding in sorted(normalized, key=_finding_sort_key):
            lines.extend(_finding_lines(finding))
    else:
        lines.extend(["No security findings were provided.", ""])

    lines.extend(
        [
            "## Commands",
            *_command_block("Observed", _extract_named_items(scan_data, ("commands", "security_commands"))),
            "",
            "## Manifests",
            *_bullet_list(_extract_named_items(scan_data, ("manifests", "manifest_files"))),
            "",
            "## Evidence",
            *_scan_evidence(scan_data),
            "",
            "## Open Questions",
            *_bullet_list(_collect_open_questions(normalized, scan_data)),
            "",
        ]
    )
    return _clean_markdown(lines)


def write_reports(
    root_path: str | Path,
    project_brief: str,
    security_audit: str,
    findings_json: list[SecurityFinding | dict[str, Any]] | dict[str, Any] | str,
    output_dir: str | Path | None = None,
) -> dict[str, Path]:
    """Write report artifacts and return their paths."""

    destination = Path(output_dir) if output_dir is not None else Path(root_path) / ".repo-check"
    destination.mkdir(parents=True, exist_ok=True)

    paths = {
        "project_brief": destination / "project_brief.md",
        "security_audit": destination / "security_audit.md",
        "findings_json": destination / "findings.json",
    }
    paths["project_brief"].write_text(project_brief, encoding="utf-8")
    paths["security_audit"].write_text(security_audit, encoding="utf-8")
    paths["findings_json"].write_text(_json_payload(findings_json), encoding="utf-8")
    return paths


def _coerce_project_profile(profile: ProjectProfile | dict[str, Any]) -> ProjectProfile:
    if isinstance(profile, ProjectProfile):
        return profile
    return ProjectProfile.model_validate(profile)


def _coerce_security_finding(finding: SecurityFinding | dict[str, Any]) -> SecurityFinding:
    if isinstance(finding, SecurityFinding):
        return finding
    return SecurityFinding.model_validate(finding)


def _bullet_line(label: str, values: list[str]) -> str:
    return f"- **{label}:** {', '.join(values) if values else 'Unknown'}"


def _bullet_list(values: list[str]) -> list[str]:
    if not values:
        return ["- None recorded."]
    return [f"- {value}" for value in values]


def _command_block(label: str, commands: list[str]) -> list[str]:
    if not commands:
        return [f"### {label}", "- None recorded."]
    return [f"### {label}", *[f"- `{command}`" for command in commands]]


def _extract_named_items(scans: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    for key in keys:
        value = scans.get(key)
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, dict):
            return [f"{name}: {detail}" for name, detail in value.items()]
        if isinstance(value, str):
            return [value]
    return []


def _scan_evidence(scans: dict[str, Any]) -> list[str]:
    evidence = _extract_named_items(scans, ("evidence", "signals", "observations"))
    if evidence:
        return _bullet_list(evidence)
    if not scans:
        return ["- No scan evidence was provided."]
    return [f"- `{key}`: {_stringify_scan_value(value)}" for key, value in sorted(scans.items())]


def _retrieval_context_lines(context: list[Any] | dict[str, Any] | str | None) -> list[str]:
    if context is None or context == [] or context == {} or context == "":
        return ["- None provided."]
    if isinstance(context, str):
        return [f"- {context}"]
    if isinstance(context, dict):
        return [f"- `{key}`: {_stringify_scan_value(value)}" for key, value in sorted(context.items())]
    return [f"- {_context_item(item)}" for item in context]


def _context_item(item: Any) -> str:
    if isinstance(item, BaseModel):
        data = item.model_dump()
    elif isinstance(item, dict):
        data = item
    else:
        return str(item)

    source = data.get("source") or data.get("file") or data.get("path") or "unknown source"
    score = data.get("score")
    content = str(data.get("content") or data.get("text") or "").strip()
    prefix = f"{source}"
    if score is not None:
        prefix = f"{prefix} (score: {score})"
    return f"{prefix}: {content[:240]}" if content else prefix


def _severity_summary(findings: list[SecurityFinding]) -> list[str]:
    counts = {severity: 0 for severity in SEVERITY_ORDER}
    for finding in findings:
        counts[finding.severity] += 1
    return [f"- **{severity.title()}:** {counts[severity]}" for severity in SEVERITY_ORDER]


def _finding_sort_key(finding: SecurityFinding) -> tuple[int, str]:
    return (SEVERITY_ORDER.index(finding.severity), finding.id)


def _finding_lines(finding: SecurityFinding) -> list[str]:
    lines = [
        "",
        f"### [{finding.severity.upper()}] {finding.title}",
        f"- **ID:** `{finding.id}`",
    ]
    if finding.description:
        lines.append(f"- **Description:** {finding.description}")
    if finding.files:
        lines.append(f"- **Files:** {', '.join(f'`{file}`' for file in finding.files)}")
    if finding.recommendation:
        lines.append(f"- **Recommendation:** {finding.recommendation}")
    lines.extend(["", "#### Evidence", *_bullet_list(finding.evidence)])
    lines.extend(["", "#### Commands", *_command_block("Finding", finding.commands)[1:]])
    if finding.open_questions:
        lines.extend(["", "#### Open Questions", *_bullet_list(finding.open_questions)])
    lines.append("")
    return lines


def _collect_open_questions(
    findings: list[SecurityFinding],
    scans: dict[str, Any],
) -> list[str]:
    questions = [question for finding in findings for question in finding.open_questions]
    questions.extend(_extract_named_items(scans, ("open_questions", "questions")))
    return questions


def _stringify_scan_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _json_payload(payload: list[SecurityFinding | dict[str, Any]] | dict[str, Any] | str) -> str:
    if isinstance(payload, str):
        return payload if payload.endswith("\n") else f"{payload}\n"
    if isinstance(payload, list):
        serializable = [
            item.model_dump(mode="json") if isinstance(item, BaseModel) else item for item in payload
        ]
    elif isinstance(payload, BaseModel):
        serializable = payload.model_dump(mode="json")
    else:
        serializable = payload
    return f"{json.dumps(serializable, indent=2, sort_keys=True)}\n"


def _clean_markdown(lines: list[str]) -> str:
    cleaned: list[str] = []
    previous_blank = False
    for line in lines:
        blank = line == ""
        if blank and previous_blank:
            continue
        cleaned.append(line.rstrip())
        previous_blank = blank
    return "\n".join(cleaned).strip() + "\n"
