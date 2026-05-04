"""Local regex and entropy-ish secret scanner with redacted evidence."""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

from pydantic import Field

from dev_rag.repo_intel.tools._common import ToolModel, is_binary_bytes, relative_to_root, root_path
from dev_rag.repo_intel.tools.repo_scanner import DEFAULT_IGNORES

SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "aws_access_key_id": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "generic_assignment": re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"]?([A-Za-z0-9_\-./+=]{16,})"
    ),
}


class SecretFinding(ToolModel):
    path: str
    line: int
    kind: str
    evidence: str
    confidence: str


class SecretScanRequest(ToolModel):
    root: str
    max_files: int = Field(default=500, ge=1)
    max_bytes_per_file: int = Field(default=500_000, ge=1)
    ignores: set[str] = Field(default_factory=lambda: set(DEFAULT_IGNORES))


class SecretScanResult(ToolModel):
    findings: list[SecretFinding] = Field(default_factory=list)
    files_scanned: int = 0
    truncated: bool = False


def _is_ignored(rel: str, ignores: set[str]) -> bool:
    parts = rel.split("/")
    return any(pattern == rel or pattern in parts for pattern in ignores)


def _redact(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _entropy(value: str) -> float:
    counts = Counter(value)
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


async def scan_secrets(request: SecretScanRequest) -> SecretScanResult:
    root = root_path(request.root)
    findings: list[SecretFinding] = []
    scanned = 0
    files = [p for p in sorted(root.rglob("*"), key=lambda item: item.as_posix()) if p.is_file()]
    for path in files:
        if scanned >= request.max_files:
            return SecretScanResult(findings=findings, files_scanned=scanned, truncated=True)
        rel = relative_to_root(root, path)
        if _is_ignored(rel, request.ignores):
            continue
        data = path.read_bytes()[: request.max_bytes_per_file]
        if is_binary_bytes(data):
            continue
        scanned += 1
        for line_no, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), start=1):
            for kind, pattern in SECRET_PATTERNS.items():
                for match in pattern.finditer(line):
                    secret = match.group(2) if kind == "generic_assignment" and match.lastindex else match.group(0)
                    confidence = "high" if kind != "generic_assignment" or _entropy(secret) >= 3.2 else "medium"
                    findings.append(
                        SecretFinding(
                            path=rel,
                            line=line_no,
                            kind=kind,
                            evidence=line.replace(secret, _redact(secret)),
                            confidence=confidence,
                        )
                    )
    return SecretScanResult(findings=findings, files_scanned=scanned)

