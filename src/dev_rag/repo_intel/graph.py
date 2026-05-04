"""LangGraph-compatible orchestration for local repository intelligence."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from dev_rag.repo_intel.state import AgentState, RepoIntelMode

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 10


async def _call_tool(name: str, payload: Any) -> Any:
    """Call deterministic tools with robust error conversion."""

    try:
        if name == "repo_scanner":
            from dev_rag.repo_intel.tools.repo_scanner import RepoScanRequest, scan_repo

            return await scan_repo(RepoScanRequest.model_validate(payload))
        if name == "manifest_parser":
            from dev_rag.repo_intel.tools.manifest_parser import ManifestParseRequest, parse_manifests

            return await parse_manifests(ManifestParseRequest.model_validate(payload))
        if name == "secret_scanner":
            from dev_rag.repo_intel.tools.secret_scanner import SecretScanRequest, scan_secrets

            return await scan_secrets(SecretScanRequest.model_validate(payload))
        if name == "script_risk_scanner":
            from dev_rag.repo_intel.tools.script_risk_scanner import (
                RiskScanRequest,
                scan_script_risks,
            )

            return await scan_script_risks(RiskScanRequest.model_validate(payload))
        if name == "rag_indexer":
            from dev_rag.repo_intel.rag import IndexRepositoryInput, index_repository

            return await index_repository(IndexRepositoryInput.model_validate(payload))
        if name == "rag_retriever":
            from dev_rag.repo_intel.rag import RetrieveInput, retrieve

            return await retrieve(RetrieveInput.model_validate(payload))
    except Exception as exc:  # noqa: BLE001 - convert tool failures into agent-observable errors.
        logger.exception("Error while executing tool=%s", name)
        return {"error": f"Error: {exc}. Please correct your syntax and try again."}

    return {"error": f"Error: unknown tool {name}. Please correct your syntax and try again."}


async def _agent_node(state: AgentState) -> AgentState:
    """Plan the next deterministic action for the selected mode."""

    iteration = state.get("iteration_count", 0) + 1
    state["iteration_count"] = iteration
    logger.info("Thought: mode=%s iteration=%s", state.get("mode"), iteration)
    if iteration > MAX_ITERATIONS:
        state["status"] = "Failure: Maximum iterations reached"
        return state

    mode = state["mode"]
    plan = ["scan_repository"]
    if mode in {"index", "onboard", "full", "ask"}:
        plan.append("index_repository")
    if mode in {"onboard", "full"}:
        plan.append("parse_manifests")
    if mode in {"audit", "full"}:
        plan.extend(["scan_secrets", "scan_script_risks"])
    if mode == "ask":
        plan.append("retrieve_context")
    if mode in {"onboard", "audit", "full"}:
        plan.append("write_reports")
    state["plan"] = plan
    return state


async def _tool_executor_node(state: AgentState, force_rebuild: bool) -> AgentState:
    """Execute planned tools and keep failures inside state."""

    root_path = state["root_path"]
    mode = state["mode"]
    logger.info("Action: executing plan=%s", state.get("plan", []))

    scan = await _call_tool("repo_scanner", {"root": root_path})
    state["scan"] = _model_or_dict(scan)
    if _has_error(scan, state):
        return state

    if mode in {"index", "onboard", "full", "ask"}:
        index = await _call_tool(
            "rag_indexer",
            {"repo_path": root_path},
        )
        state.setdefault("reports", {})["index"] = str(_get_attr(index, "index_path", ""))
        if _has_error(index, state):
            return state

    if mode in {"onboard", "full"}:
        profile = await _call_tool(
            "manifest_parser",
            {"root": root_path},
        )
        state["profile"] = _model_or_dict(profile)
        if _has_error(profile, state):
            return state

    findings: list[dict[str, Any]] = []
    if mode in {"audit", "full"}:
        secret_result = await _call_tool("secret_scanner", {"root": root_path})
        script_result = await _call_tool("script_risk_scanner", {"root": root_path})
        for result in (secret_result, script_result):
            if _has_error(result, state):
                return state
            findings.extend(_model_or_dict(item) for item in _get_attr(result, "findings", []))
        state["findings"] = findings

    if mode == "ask":
        question = state.get("question") or "What is this repository about?"
        retrieved = await _call_tool(
            "rag_retriever",
            {"repo_path": root_path, "query": question, "top_k": 8, "mode": "ask"},
        )
        if _has_error(retrieved, state):
            return state
        chunks = [_model_or_dict(item) for item in _get_attr(retrieved, "results", [])]
        state["retrieved_context"] = chunks
        state["reports"] = {"answer": _answer_from_chunks(question, chunks)}

    if mode in {"onboard", "audit", "full"}:
        await _write_reports(state)

    logger.info("Observation: plan executed status=%s", state.get("status", "pending"))
    return state


async def _critic_node(state: AgentState) -> AgentState:
    """Validate that required artifacts exist for the selected mode."""

    if state.get("error_log"):
        state["status"] = "error"
        logger.error("Error: %s", state["error_log"][-1])
        return state
    mode = state["mode"]
    reports = state.get("reports", {})
    if mode == "ask" and not reports.get("answer"):
        state["status"] = "error"
        state.setdefault("error_log", []).append("No answer generated")
        return state
    if mode in {"onboard", "full"} and "project_brief" not in reports:
        state["status"] = "error"
        state.setdefault("error_log", []).append("Project brief was not generated")
        return state
    if mode in {"audit", "full"} and "security_audit" not in reports:
        state["status"] = "error"
        state.setdefault("error_log", []).append("Security audit was not generated")
        return state
    state["status"] = "ok"
    return state


async def _write_reports(state: AgentState) -> None:
    """Render reports through the report module when available."""

    try:
        from dev_rag.repo_intel.reports import (
            render_project_brief,
            render_security_audit,
            write_reports,
        )

        root = Path(state["root_path"])
        project_brief = ""
        security_audit = ""
        if state["mode"] in {"onboard", "full"}:
            project_brief = render_project_brief(
                _project_profile_from_state(state),
                _scan_summary_from_state(state),
                state.get("retrieved_context", []),
            )
        if state["mode"] in {"audit", "full"}:
            security_audit = render_security_audit(
                [_report_finding(finding) for finding in state.get("findings", [])],
                _scan_summary_from_state(state),
            )
        paths = write_reports(
            root,
            project_brief,
            security_audit,
            state.get("findings", []),
            state.get("output_dir"),
        )
        state["reports"] = {key: str(value) for key, value in paths.items()}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error: report generation failed")
        state.setdefault("error_log", []).append(f"report generation failed: {exc}")


def _model_or_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    return {"value": value}


def _get_attr(value: Any, name: str, default: Any) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _has_error(value: Any, state: AgentState) -> bool:
    data = _model_or_dict(value)
    error = data.get("error")
    if error:
        state.setdefault("error_log", []).append(str(error))
        return True
    return False


def _answer_from_chunks(question: str, chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return f"No local context found for: {question}"
    lines = [f"Question: {question}", "", "Relevant local context:"]
    for chunk in chunks:
        source = chunk.get("path", "unknown")
        start = chunk.get("start_line", "?")
        end = chunk.get("end_line", "?")
        text = str(chunk.get("text", "")).strip().replace("\n", " ")
        lines.append(f"- {source}:{start}-{end}: {text[:300]}")
    return "\n".join(lines)


def _project_profile_from_state(state: AgentState) -> dict[str, Any]:
    root = Path(state["root_path"])
    profile = state.get("profile", {})
    manifests = profile.get("manifests", []) if isinstance(profile, dict) else []
    return {
        "name": root.name,
        "summary": "Local repository profile generated from deterministic manifest and file scans.",
        "languages": profile.get("languages", []) if isinstance(profile, dict) else [],
        "frameworks": _infer_frameworks(profile),
        "package_managers": profile.get("package_managers", []) if isinstance(profile, dict) else [],
        "entrypoints": _entrypoints_from_scan(state.get("scan", {})),
        "test_commands": profile.get("test_commands", []) if isinstance(profile, dict) else [],
        "build_commands": profile.get("build_commands", []) if isinstance(profile, dict) else [],
        "run_commands": profile.get("run_commands", []) if isinstance(profile, dict) else [],
        "manifests": [
            str(item.get("path", item)) if isinstance(item, dict) else str(item) for item in manifests
        ],
        "open_questions": [],
        "evidence": ["Generated by repo_scanner, manifest_parser, and local RAG index."],
    }


def _infer_frameworks(profile: dict[str, Any] | object) -> list[str]:
    if not isinstance(profile, dict):
        return []
    deps = {str(dep).lower() for dep in profile.get("dependencies", [])}
    known = {
        "fastapi": "FastAPI",
        "django": "Django",
        "flask": "Flask",
        "react": "React",
        "next": "Next.js",
        "langgraph": "LangGraph",
        "langchain": "LangChain",
        "qdrant-client": "Qdrant",
    }
    return sorted(label for dep, label in known.items() if dep in deps)


def _entrypoints_from_scan(scan: dict[str, Any] | object) -> list[str]:
    if not isinstance(scan, dict):
        return []
    files = scan.get("files", [])
    paths = [item.get("path", "") if isinstance(item, dict) else str(item) for item in files]
    candidates = {"main.py", "app.py", "src/main.py", "src/app.py", "package.json", "pyproject.toml"}
    return [path for path in paths if path in candidates or path.endswith("/cli.py")][:20]


def _scan_summary_from_state(state: AgentState) -> dict[str, Any]:
    scan = state.get("scan", {})
    profile = state.get("profile", {})
    files = scan.get("files", []) if isinstance(scan, dict) else []
    dirs = scan.get("dirs", []) if isinstance(scan, dict) else []
    return {
        "files_scanned": len(files),
        "directories_seen": len(dirs),
        "manifests": [
            str(item.get("path", item))
            for item in (profile.get("manifests", []) if isinstance(profile, dict) else [])
        ],
        "commands": (
            (profile.get("run_commands", []) if isinstance(profile, dict) else [])
            + (profile.get("test_commands", []) if isinstance(profile, dict) else [])
            + (profile.get("build_commands", []) if isinstance(profile, dict) else [])
        ),
    }


def _report_finding(finding: dict[str, Any]) -> dict[str, Any]:
    kind = str(finding.get("kind", "finding"))
    path = str(finding.get("path", "unknown"))
    line = finding.get("line")
    severity = str(finding.get("severity", "medium"))
    if severity not in {"critical", "high", "medium", "low", "info"}:
        severity = "medium"
    return {
        "id": f"{kind}:{path}:{line}",
        "title": kind.replace("_", " ").title(),
        "severity": severity,
        "description": "Local scanner detected a potential repository security risk.",
        "evidence": [str(finding.get("evidence", ""))],
        "files": [f"{path}:{line}" if line else path],
        "recommendation": "Review this finding manually and remove or constrain the risky pattern if it is not intentional.",
    }


async def run_repo_intel(
    mode: RepoIntelMode,
    root_path: Path,
    question: str | None = None,
    force_rebuild: bool = False,
    output_dir: Path | None = None,
) -> dict[str, object]:
    """Run the repository intelligence workflow."""

    resolved = root_path.resolve()
    if not resolved.exists() or not resolved.is_dir():
        return {"status": "error", "error_log": [f"Repository path does not exist: {resolved}"]}

    state: AgentState = {
        "messages": [],
        "plan": [],
        "iteration_count": 0,
        "error_log": [],
        "root_path": str(resolved),
        "output_dir": str(output_dir.expanduser().resolve()) if output_dir else None,
        "mode": mode,
        "question": question,
        "reports": {},
    }

    try:
        from langgraph.graph import END, StateGraph

        async def tools_node(graph_state: AgentState) -> AgentState:
            return await _tool_executor_node(graph_state, force_rebuild)

        graph = StateGraph(AgentState)
        graph.add_node("agent", _agent_node)
        graph.add_node("tools", tools_node)
        graph.add_node("critic", _critic_node)
        graph.set_entry_point("agent")
        graph.add_edge("agent", "tools")
        graph.add_edge("tools", "critic")
        graph.add_edge("critic", END)
        compiled = graph.compile()
        final_state = await compiled.ainvoke(state)
    except ImportError:
        logger.info("LangGraph is not installed; using deterministic fallback runner")
        final_state = await _critic_node(await _tool_executor_node(await _agent_node(state), force_rebuild))

    result: dict[str, object] = {
        "status": final_state.get("status", "error"),
        "reports": final_state.get("reports", {}),
        "error_log": final_state.get("error_log", []),
    }
    if mode == "ask":
        result["answer"] = final_state.get("reports", {}).get("answer", "")
    return json.loads(json.dumps(result, default=str))
