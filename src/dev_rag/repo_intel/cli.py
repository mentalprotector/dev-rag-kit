"""CLI for local repository onboarding, audit, indexing, and Q&A."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from dev_rag.repo_intel.graph import run_repo_intel


def _print_result(title: str, result: dict[str, object]) -> None:
    separator = "=" * 88
    print(f"\n{separator}\n{title}\n{separator}")
    status = result.get("status", "unknown")
    print(f"Status: {status}")
    reports = result.get("reports")
    if isinstance(reports, dict) and reports:
        for name, path in reports.items():
            if name == "answer":
                continue
            print(f"{name}: {path}")
    answer = result.get("answer")
    if answer:
        print(f"\n{answer}")


async def _run(args: argparse.Namespace) -> int:
    if args.command == "web":
        from dev_rag.repo_intel.web import run_web

        run_web(args.host, args.port)
        return 0

    result = await run_repo_intel(
        mode=args.command,
        root_path=Path(args.root_path),
        question=getattr(args, "question", None),
        force_rebuild=getattr(args, "force", False),
        output_dir=getattr(args, "output", None),
    )
    _print_result(f"Repo Check: {args.command}", result)
    return 0 if result.get("status") == "ok" else 1


def build_parser() -> argparse.ArgumentParser:
    """Build the repository intelligence parser."""

    parser = argparse.ArgumentParser(description="Local Repository Intelligence Agent.")
    parser.add_argument("--verbose", action="store_true", help="Enable INFO logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("index", "onboard", "audit", "full"):
        sub = subparsers.add_parser(command, help=f"Run {command} workflow")
        sub.add_argument("root_path", help="Repository path to inspect")
        sub.add_argument("--force", action="store_true", help="Rebuild local index")
        sub.add_argument(
            "--output",
            type=Path,
            default=None,
            help="Report output directory; defaults to <repo>/.repo-check",
        )

    ask = subparsers.add_parser("ask", help="Ask a question about a repository")
    ask.add_argument("root_path", help="Repository path to inspect")
    ask.add_argument("question", help="Question to answer from the local repository index")
    ask.add_argument("--force", action="store_true", help="Rebuild local index before answering")
    ask.add_argument(
        "--output",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )

    web = subparsers.add_parser("web", help="Run browser UI server")
    web.add_argument("--host", default="127.0.0.1", help="Bind host; use 0.0.0.0 for LAN access")
    web.add_argument("--port", type=int, default=8765, help="Bind port")

    return parser


def main() -> None:
    """Run the repository intelligence CLI."""

    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
