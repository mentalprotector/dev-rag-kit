"""Backward-compatible CLI for running RAGAS evaluation."""

from __future__ import annotations

import sys

from dev_rag.cli import main as unified_main


def main() -> None:
    """Run the unified CLI in evaluate mode for legacy command compatibility."""

    sys.argv.insert(1, "evaluate")
    unified_main()


if __name__ == "__main__":
    main()
