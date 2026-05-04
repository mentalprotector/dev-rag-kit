"""Scan local scripts and configs for risky command patterns."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import Field

from second_brain.repo_intel.tools._common import ToolModel, is_binary_bytes, relative_to_root, root_path
from second_brain.repo_intel.tools.repo_scanner import DEFAULT_IGNORES

RISK_PATTERNS: dict[str, re.Pattern[str]] = {
    "curl_pipe_shell": re.compile(r"\bcurl\b[^\n|;]*\|\s*(?:sh|bash)\b", re.IGNORECASE),
    "wget_pipe_shell": re.compile(r"\bwget\b[^\n|;]*\|\s*(?:sh|bash)\b", re.IGNORECASE),
    "rm_rf": re.compile(r"\brm\s+-[A-Za-z]*r[A-Za-z]*f|\brm\s+-[A-Za-z]*f[A-Za-z]*r", re.IGNORECASE),
    "chmod_777": re.compile(r"\bchmod\s+777\b"),
    "sudo": re.compile(r"\bsudo\b"),
    "eval": re.compile(r"\beval\b"),
    "invoke_expression": re.compile(r"\bInvoke-Expression\b|\biex\b", re.IGNORECASE),
    "set_execution_policy_bypass": re.compile(r"\bSet-ExecutionPolicy\b.*\bBypass\b", re.IGNORECASE),
    "docker_privileged": re.compile(r"--privileged\b"),
    "docker_sock": re.compile(r"docker\.sock|/var/run/docker\.sock"),
}

SCRIPT_EXTENSIONS = {
    ".sh",
    ".bash",
    ".zsh",
    ".ps1",
    ".bat",
    ".cmd",
    ".yml",
    ".yaml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".dockerfile",
}
SCRIPT_NAMES = {"Dockerfile", "Makefile", "package.json", "pyproject.toml"}


class RiskFinding(ToolModel):
    path: str
    line: int
    kind: str
    evidence: str
    severity: str


class RiskScanRequest(ToolModel):
    root: str
    max_files: int = Field(default=500, ge=1)
    max_bytes_per_file: int = Field(default=500_000, ge=1)
    ignores: set[str] = Field(default_factory=lambda: set(DEFAULT_IGNORES))


class RiskScanResult(ToolModel):
    findings: list[RiskFinding] = Field(default_factory=list)
    files_scanned: int = 0
    truncated: bool = False


def _is_ignored(rel: str, ignores: set[str]) -> bool:
    parts = rel.split("/")
    return any(pattern == rel or pattern in parts for pattern in ignores)


def _is_script_like(path: Path) -> bool:
    return path.name in SCRIPT_NAMES or path.suffix.lower() in SCRIPT_EXTENSIONS


def _severity(kind: str) -> str:
    if kind in {"curl_pipe_shell", "wget_pipe_shell", "set_execution_policy_bypass", "docker_sock"}:
        return "high"
    if kind in {"rm_rf", "docker_privileged", "eval", "invoke_expression"}:
        return "medium"
    return "low"


async def scan_script_risks(request: RiskScanRequest) -> RiskScanResult:
    root = root_path(request.root)
    findings: list[RiskFinding] = []
    scanned = 0
    files = [p for p in sorted(root.rglob("*"), key=lambda item: item.as_posix()) if p.is_file()]
    for path in files:
        if scanned >= request.max_files:
            return RiskScanResult(findings=findings, files_scanned=scanned, truncated=True)
        rel = relative_to_root(root, path)
        if _is_ignored(rel, request.ignores) or not _is_script_like(path):
            continue
        data = path.read_bytes()[: request.max_bytes_per_file]
        if is_binary_bytes(data):
            continue
        scanned += 1
        for line_no, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), start=1):
            for kind, pattern in RISK_PATTERNS.items():
                if pattern.search(line):
                    findings.append(
                        RiskFinding(
                            path=rel,
                            line=line_no,
                            kind=kind,
                            evidence=line.strip()[:240],
                            severity=_severity(kind),
                        )
                    )
    return RiskScanResult(findings=findings, files_scanned=scanned)

