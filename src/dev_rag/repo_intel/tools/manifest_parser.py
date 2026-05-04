"""Parse common repository manifests into deterministic metadata."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field

from dev_rag.repo_intel.tools._common import ToolModel, relative_to_root, root_path

MANIFEST_NAMES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}


def _dependency_name(value: str) -> str:
    return (
        value.split(";", 1)[0]
        .split("[", 1)[0]
        .split("==", 1)[0]
        .split(">=", 1)[0]
        .split("<=", 1)[0]
        .split("~=", 1)[0]
        .split("!=", 1)[0]
        .split("<", 1)[0]
        .split(">", 1)[0]
        .strip()
    )


class ManifestInfo(ToolModel):
    path: str
    kind: str
    languages: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    scripts: dict[str, str] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    run_commands: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    build_commands: list[str] = Field(default_factory=list)


class ManifestParseRequest(ToolModel):
    root: str
    max_files: int = Field(default=200, ge=1)


class ManifestParseResult(ToolModel):
    manifests: list[ManifestInfo] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    run_commands: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    build_commands: list[str] = Field(default_factory=list)


def _strings(values: Any) -> list[str]:
    if isinstance(values, dict):
        return sorted(str(k) for k in values)
    if isinstance(values, list):
        return sorted(str(v) for v in values)
    return []


def _classify_script(name: str, command: str, info: ManifestInfo) -> None:
    lowered = name.lower()
    entry = f"{name}: {command}"
    if "test" in lowered:
        info.test_commands.append(entry)
    if "build" in lowered:
        info.build_commands.append(entry)
    if lowered in {"start", "dev", "serve", "run"}:
        info.run_commands.append(entry)


def _parse_package_json(path: Path, rel: str) -> ManifestInfo:
    data = json.loads(path.read_text(encoding="utf-8"))
    info = ManifestInfo(path=rel, kind="package.json", languages=["JavaScript"], package_managers=["npm"])
    if (path.parent / "yarn.lock").exists():
        info.package_managers.append("yarn")
    if (path.parent / "pnpm-lock.yaml").exists():
        info.package_managers.append("pnpm")
    scripts = data.get("scripts") if isinstance(data, dict) else {}
    if isinstance(scripts, dict):
        info.scripts = {str(k): str(v) for k, v in sorted(scripts.items())}
        for name, command in info.scripts.items():
            _classify_script(name, command, info)
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        info.dependencies.extend(_strings(data.get(key)))
    info.dependencies = sorted(set(info.dependencies))
    return info


def _parse_pyproject(path: Path, rel: str) -> ManifestInfo:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    info = ManifestInfo(path=rel, kind="pyproject.toml", languages=["Python"], package_managers=["pip"])
    build_backend = data.get("build-system", {}).get("build-backend", "")
    if "poetry" in build_backend or "poetry" in data.get("tool", {}):
        info.package_managers.append("poetry")
    if "pdm" in build_backend or "pdm" in data.get("tool", {}):
        info.package_managers.append("pdm")
    project = data.get("project", {})
    info.dependencies.extend(_dependency_name(str(dep)) for dep in project.get("dependencies", []))
    scripts = project.get("scripts", {})
    if isinstance(scripts, dict):
        info.scripts = {str(k): str(v) for k, v in sorted(scripts.items())}
        for name, command in info.scripts.items():
            _classify_script(name, command, info)
    return info


def _parse_requirements(path: Path, rel: str) -> ManifestInfo:
    deps = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        clean = line.strip()
        if clean and not clean.startswith(("#", "-", "http://", "https://")):
            deps.append(_dependency_name(clean))
    return ManifestInfo(
        path=rel,
        kind="requirements.txt",
        languages=["Python"],
        package_managers=["pip"],
        dependencies=sorted(set(deps)),
    )


def _parse_dockerfile(path: Path, rel: str) -> ManifestInfo:
    commands = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.upper().startswith(("RUN ", "CMD ", "ENTRYPOINT ")):
            commands.append(stripped)
    return ManifestInfo(path=rel, kind="Dockerfile", package_managers=["docker"], run_commands=commands)


def _parse_compose(path: Path, rel: str) -> ManifestInfo:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    commands = []
    for name, service in (data.get("services") or {}).items():
        if isinstance(service, dict):
            for key in ("command", "entrypoint"):
                if key in service:
                    commands.append(f"{name}.{key}: {service[key]}")
    return ManifestInfo(path=rel, kind=path.name, package_managers=["docker compose"], run_commands=commands)


def _parse_action(path: Path, rel: str) -> ManifestInfo:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    info = ManifestInfo(path=rel, kind="github-actions")
    for job_name, job in (data.get("jobs") or {}).items():
        for step in (job or {}).get("steps", []):
            if isinstance(step, dict) and "run" in step:
                command = f"{job_name}: {step['run']}"
                info.run_commands.append(command)
                lowered = command.lower()
                if "test" in lowered:
                    info.test_commands.append(command)
                if "build" in lowered:
                    info.build_commands.append(command)
    return info


def _parse_one(root: Path, path: Path) -> ManifestInfo | None:
    rel = relative_to_root(root, path)
    if path.name == "package.json":
        return _parse_package_json(path, rel)
    if path.name == "pyproject.toml":
        return _parse_pyproject(path, rel)
    if path.name == "requirements.txt":
        return _parse_requirements(path, rel)
    if path.name == "Dockerfile":
        return _parse_dockerfile(path, rel)
    if path.name in {"docker-compose.yml", "docker-compose.yaml"}:
        return _parse_compose(path, rel)
    if ".github/workflows/" in rel and path.suffix in {".yml", ".yaml"}:
        return _parse_action(path, rel)
    return None


async def parse_manifests(request: ManifestParseRequest) -> ManifestParseResult:
    root = root_path(request.root)
    candidates = [
        p
        for p in sorted(root.rglob("*"), key=lambda item: item.as_posix())
        if p.is_file()
        and (p.name in MANIFEST_NAMES or ".github/workflows/" in relative_to_root(root, p))
    ][: request.max_files]
    manifests = [info for path in candidates if (info := _parse_one(root, path)) is not None]
    return ManifestParseResult(
        manifests=manifests,
        languages=sorted({v for m in manifests for v in m.languages}),
        package_managers=sorted({v for m in manifests for v in m.package_managers}),
        dependencies=sorted({v for m in manifests for v in m.dependencies}),
        run_commands=sorted({v for m in manifests for v in m.run_commands}),
        test_commands=sorted({v for m in manifests for v in m.test_commands}),
        build_commands=sorted({v for m in manifests for v in m.build_commands}),
    )
