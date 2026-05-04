"""Unified CLI for the complete Dev RAG Kit workflow."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dev_rag.app import build_evaluator, build_orchestrator
from dev_rag.config import load_config
from dev_rag.evaluation.evaluator import EvaluationReport
from dev_rag.orchestration.llm_client import LLMClient
from dev_rag.orchestration.llm_client import LLMClientError
from dev_rag.orchestration.orchestrator import RAGResponse
from dev_rag.retrieval.manifest import load_chunk_manifest


def _print_section(title: str, body: str) -> None:
    """Print a visually separated terminal section."""

    separator = "=" * 88
    print(f"\n{separator}\n{title}\n{separator}\n{body.strip() or '<empty>'}")


def _print_step(index: int, title: str) -> None:
    """Print an E2E workflow step title."""

    print(f"\n[{index}/3] {title}")
    print("-" * 88)


def _cmd_status(args: argparse.Namespace) -> int:
    """Show current configuration and local manifest status."""

    config = load_config(args.config)
    chunks = load_chunk_manifest(config.chunking.manifest_path, warn_missing=False)
    _print_section(
        "Dev RAG Status",
        "\n".join(
            [
                f"Qdrant URL: {config.qdrant.url}",
                f"Collection: {config.qdrant.collection}",
                f"Embedding model: {config.embedding.model_name}",
                f"LLM URL: {config.llm.api_base_url}",
                f"LLM model: {config.llm.model_name}",
                f"Chunk manifest: {config.chunking.manifest_path}",
                f"Manifest chunks: {len(chunks)}",
                "Knowledge loaded: no" if not chunks else "Knowledge loaded: yes",
            ]
        ),
    )
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    """Check live infrastructure connectivity."""

    config = load_config(args.config)
    checks: list[str] = []
    ok = True

    try:
        from qdrant_client import QdrantClient

        qdrant = QdrantClient(url=str(config.qdrant.url), timeout=5)
        collections = qdrant.get_collections()
        checks.append(f"Qdrant: ok ({len(collections.collections)} collections visible)")
    except Exception as exc:
        ok = False
        checks.append(f"Qdrant: failed ({exc})")

    try:
        llm = LLMClient(
            api_base_url=str(config.llm.api_base_url),
            model_name=config.llm.model_name,
            timeout_seconds=min(config.llm.timeout_seconds, 10),
        )
        models = llm.list_models()
        model_status = "loaded" if config.llm.model_name in models else "not listed"
        checks.append(f"LM Studio: ok ({len(models)} models, target model {model_status})")
        checks.append(f"LM Studio URL: {config.llm.api_base_url}")
    except LLMClientError as exc:
        ok = False
        checks.append(f"LM Studio: failed ({exc})")

    chunks = load_chunk_manifest(config.chunking.manifest_path, warn_missing=False)
    checks.append(f"Chunk manifest: {len(chunks)} chunks at {config.chunking.manifest_path}")
    _print_section("Dev RAG Doctor", "\n".join(checks))
    return 0 if ok else 1


def _cmd_ingest(args: argparse.Namespace) -> int:
    """Run ingestion from the unified CLI."""

    from dev_rag.ingestion.pipeline import IngestionPipeline

    config = load_config(args.config)
    uploaded = IngestionPipeline(config).ingest_file(args.document)
    _print_section("Ingestion Complete", f"Uploaded chunks: {uploaded}\nManifest: {config.chunking.manifest_path}")
    return 0


def _ask_once(args: argparse.Namespace) -> RAGResponse:
    """Ask one question and print the full RAG trace."""

    config = load_config(args.config)
    response = build_orchestrator(config).answer(
        args.question,
        hybrid_limit=args.hybrid_limit,
        final_limit=args.final_limit,
    )
    _print_section("Question", response.question)
    _print_section("Retrieved Context", response.context)
    _print_section("Final Answer", response.answer)
    return response


def _cmd_ask(args: argparse.Namespace) -> int:
    """Run a single RAG question."""

    try:
        _ask_once(args)
    except (ValueError, LLMClientError) as exc:
        _print_section("Error", str(exc))
        return 1
    return 0


def _cmd_chat(args: argparse.Namespace) -> int:
    """Run an interactive RAG chat loop."""

    print("Dev RAG Kit. Type 'exit' or 'quit' to stop.")
    try:
        while True:
            question = input("\nQuestion> ").strip()
            if question.lower() in {"exit", "quit"}:
                return 0
            if not question:
                continue
            args.question = question
            if _cmd_ask(args) != 0:
                return 1
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


def _cmd_evaluate(args: argparse.Namespace) -> int:
    """Run RAGAS evaluation from the unified CLI."""

    config = load_config(args.config)
    report = build_evaluator(config, args.output).evaluate_file(args.dataset)
    return 0 if report.failed_count == 0 else 1


def _cmd_e2e(args: argparse.Namespace) -> int:
    """Run the full document -> answer -> evaluation workflow."""

    _print_step(1, "Ingest document")
    ingest_args = argparse.Namespace(config=args.config, document=args.document)
    _cmd_ingest(ingest_args)

    _print_step(2, "Ask question")
    ask_args = argparse.Namespace(
        config=args.config,
        question=args.question,
        hybrid_limit=args.hybrid_limit,
        final_limit=args.final_limit,
    )
    try:
        _ask_once(ask_args)
    except (ValueError, LLMClientError) as exc:
        _print_section("E2E Failed During Ask", str(exc))
        return 1

    _print_step(3, "Run RAGAS audit")
    config = load_config(args.config)
    report: EvaluationReport = build_evaluator(config, args.output).evaluate_file(args.dataset)
    _print_section("E2E Complete", f"Final audit report: {report.output_path}")
    return 0 if report.failed_count == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    """Build the unified CLI parser."""

    parser = argparse.ArgumentParser(description="Dev RAG Kit unified CLI.")
    parser.add_argument("--config", default="config/default.yaml", help="Path to YAML config")
    parser.add_argument("--verbose", action="store_true", help="Enable INFO logs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Show config and ingestion status")
    status.set_defaults(func=_cmd_status)

    doctor = subparsers.add_parser("doctor", help="Check Qdrant, LM Studio, and local manifest")
    doctor.set_defaults(func=_cmd_doctor)

    ingest = subparsers.add_parser("ingest", help="Ingest a Markdown or text document")
    ingest.add_argument("document", help="Path to .md or .txt document")
    ingest.set_defaults(func=_cmd_ingest)

    ask = subparsers.add_parser("ask", help="Ask one question")
    ask.add_argument("question", help="Question to answer")
    ask.add_argument("--hybrid-limit", type=int, default=20)
    ask.add_argument("--final-limit", type=int, default=5)
    ask.set_defaults(func=_cmd_ask)

    chat = subparsers.add_parser("chat", help="Start interactive RAG CLI")
    chat.add_argument("--hybrid-limit", type=int, default=20)
    chat.add_argument("--final-limit", type=int, default=5)
    chat.set_defaults(func=_cmd_chat)

    evaluate = subparsers.add_parser("evaluate", help="Run RAGAS audit")
    evaluate.add_argument("dataset", help="Path to gold-standard JSON or CSV")
    evaluate.add_argument("--output", default="evaluation_results.json")
    evaluate.set_defaults(func=_cmd_evaluate)

    e2e = subparsers.add_parser("e2e", help="Run ingest, ask, and evaluation in one command")
    e2e.add_argument("--document", required=True, help="Path to document to ingest")
    e2e.add_argument("--question", required=True, help="Question to ask after ingestion")
    e2e.add_argument("--dataset", required=True, help="Gold-standard JSON or CSV dataset")
    e2e.add_argument("--output", default="final_audit_report.json")
    e2e.add_argument("--hybrid-limit", type=int, default=20)
    e2e.add_argument("--final-limit", type=int, default=5)
    e2e.set_defaults(func=_cmd_e2e)

    return parser


def main() -> None:
    """Run the unified CLI."""

    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
