"""Shared state for the repository intelligence LangGraph workflow."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

try:
    from langchain_core.messages import BaseMessage
except ImportError:  # pragma: no cover - fallback keeps deterministic CLI usable.
    BaseMessage = Any  # type: ignore[misc,assignment]


RepoIntelMode = Literal["index", "onboard", "audit", "full", "ask"]


class AgentState(TypedDict, total=False):
    """State passed through the repository intelligence graph."""

    messages: list[BaseMessage]
    plan: list[str]
    iteration_count: int
    error_log: list[str]
    root_path: str
    mode: RepoIntelMode
    question: str | None
    scan: dict[str, Any]
    profile: dict[str, Any]
    findings: list[dict[str, Any]]
    retrieved_context: list[dict[str, Any]]
    reports: dict[str, str]
    status: str
