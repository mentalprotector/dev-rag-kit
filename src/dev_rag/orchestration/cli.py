"""Backward-compatible interactive CLI for asking questions against the RAG pipeline."""

from __future__ import annotations

import sys

from dev_rag.cli import main as unified_main


def main() -> None:
    """Run the unified CLI in chat mode for legacy command compatibility."""

    sys.argv.insert(1, "chat")
    unified_main()


if __name__ == "__main__":
    main()
