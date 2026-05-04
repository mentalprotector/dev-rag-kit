"""Command line entry point for ingestion."""

from __future__ import annotations

import argparse
import logging

from second_brain.config import load_config
from second_brain.ingestion.pipeline import IngestionPipeline


def main() -> None:
    """Run ingestion for a single file."""

    parser = argparse.ArgumentParser(description="Ingest a Markdown or text file into Qdrant.")
    parser.add_argument("path", help="Path to a .md or .txt file")
    parser.add_argument("--config", default="config/default.yaml", help="Path to YAML config")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    config = load_config(args.config)
    uploaded = IngestionPipeline(config).ingest_file(args.path)
    logging.info("Ingestion completed uploaded_chunks=%s", uploaded)


if __name__ == "__main__":
    main()
