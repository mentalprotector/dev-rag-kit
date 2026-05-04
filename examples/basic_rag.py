"""Minimal library usage example."""

from second_brain.app import build_orchestrator
from second_brain.config import load_config
from second_brain.ingestion.pipeline import IngestionPipeline


def main() -> None:
    """Ingest one document and ask one question."""

    config = load_config("config/default.yaml")
    IngestionPipeline(config).ingest_file("examples/example.md")
    response = build_orchestrator(config).answer("What is this document about?")
    print(response.answer)


if __name__ == "__main__":
    main()
