from pathlib import Path

from second_brain.cli import build_parser
from second_brain.config import load_config
from second_brain.ingestion.schemas import Document, DocumentChunk
from second_brain.retrieval.manifest import load_chunk_manifest


def test_unified_cli_parser_supports_e2e_command() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "e2e",
            "--document",
            "data/doc.md",
            "--question",
            "What is this document about?",
            "--dataset",
            "config/gold.json",
        ]
    )

    assert args.command == "e2e"
    assert args.output == "final_audit_report.json"


def test_config_loads_chunk_manifest_path() -> None:
    config = load_config("config/default.yaml")

    assert config.chunking.manifest_path


def test_chunk_manifest_roundtrip(tmp_path: Path) -> None:
    document = Document(content="hello world", source="doc.md")
    chunk = DocumentChunk(
        document_id=document.id,
        content="hello world",
        source=document.source,
        chunk_index=0,
        timestamp=document.timestamp,
    )
    manifest = tmp_path / "chunks.jsonl"
    manifest.write_text(chunk.model_dump_json() + "\n", encoding="utf-8")

    chunks = load_chunk_manifest(manifest)

    assert len(chunks) == 1
    assert chunks[0].content == "hello world"
