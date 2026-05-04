# Dev RAG Kit

Reusable Python toolkit for local documentation RAG and lightweight repository inspection.

The project is built for local-first developer workflows:

- ingest Markdown or text documentation into Qdrant;
- retrieve relevant chunks with hybrid search;
- rerank candidates before sending context to an LLM;
- answer through an OpenAI-compatible local endpoint such as LM Studio;
- evaluate answer quality with RAGAS;
- inspect a repository and generate local onboarding/security notes.

## What You Get

### Documentation RAG

- Markdown/text ingestion with semantic-aware chunking.
- Dense retrieval with Qdrant.
- Sparse keyword retrieval with BM25.
- Reciprocal Rank Fusion to merge dense and sparse results.
- Cross-encoder reranking for final context precision.
- OpenAI-compatible LLM client for LM Studio or similar local servers.
- RAGAS evaluation for faithfulness, answer relevance, and context precision.
- Single CLI for status checks, ingestion, questions, chat, evaluation, and E2E runs.

### Repository Inspection

- Repository file scan with common noisy folders ignored.
- Manifest parsing for Python, Node, Docker, Compose, and GitHub Actions.
- Local lexical index for repository Q&A.
- Secret-pattern scan with redacted evidence.
- Risky script/config scan.
- Markdown reports and JSON findings.
- Optional FastAPI browser UI.

## Install

Python 3.10+ is required.

Minimal install:

```bash
pip install -e .
```

Full development install:

```bash
pip install -e ".[all]"
```

Install only optional groups as needed:

```bash
pip install -e ".[eval]"
pip install -e ".[web]"
pip install -e ".[repo-intel]"
```

## External Services

Start Qdrant:

```bash
docker compose up -d qdrant
```

Run LM Studio or another OpenAI-compatible server and expose `/v1`.

Example `.env`:

```env
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=dev_rag_docs
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
LLM_API_BASE_URL=http://localhost:1234/v1
LLM_MODEL_NAME=unsloth/gemma-4-26b-a4b-it
CHUNK_MANIFEST_PATH=data/chunks.jsonl
```

Check connectivity:

```bash
dev-rag doctor
```

## CLI Usage

### Documentation RAG

Show current config:

```bash
dev-rag status
```

Ingest a document:

```bash
dev-rag ingest examples/example.md
```

Ask one question:

```bash
dev-rag ask "How is the Example Service deployed?"
```

Open an interactive loop:

```bash
dev-rag chat
```

Run evaluation:

```bash
dev-rag evaluate examples/gold_standard.json --output evaluation_results.json
```

Run the full flow:

```bash
dev-rag e2e \
  --document examples/example.md \
  --question "How is the Example Service deployed?" \
  --dataset examples/gold_standard.json \
  --output final_audit_report.json
```

### Repository Check

Index a repository:

```bash
repo-check index /path/to/repo
```

Generate onboarding notes:

```bash
repo-check onboard /path/to/repo
```

Run local security checks:

```bash
repo-check audit /path/to/repo
```

Run index, onboarding, and audit together:

```bash
repo-check full /path/to/repo
```

Ask a repository question:

```bash
repo-check ask /path/to/repo "How do I run tests?"
```

Start the optional browser UI:

```bash
repo-check web --host 127.0.0.1 --port 8765
```

## Library Usage

```python
from dev_rag.app import build_orchestrator
from dev_rag.config import load_config
from dev_rag.ingestion.pipeline import IngestionPipeline

config = load_config("config/default.yaml")

uploaded_chunks = IngestionPipeline(config).ingest_file("examples/example.md")
orchestrator = build_orchestrator(config)
response = orchestrator.answer("How is the Example Service deployed?")

print(uploaded_chunks)
print(response.answer)
```

## Architecture

```text
Document files
  -> ingestion
  -> chunk manifest + Qdrant
  -> hybrid retrieval
  -> cross-encoder reranking
  -> prompt construction
  -> local OpenAI-compatible LLM
  -> answer
  -> optional RAGAS evaluation
```

Main package layout:

```text
src/dev_rag/
  ingestion/       schemas, chunking, embeddings, Qdrant upload
  retrieval/       BM25, Qdrant wrapper, RRF fusion, reranker
  orchestration/   prompt manager, LLM client, RAG orchestrator
  evaluation/      gold dataset loader and RAGAS evaluator
  repo_intel/      repository scan, index, reports, optional web UI
```

Compatibility wrappers are kept under `src/ingestion`, `src/retrieval`, `src/orchestration`, and `src/evaluation` for older imports.

## Configuration

Default config lives in `config/default.yaml` and expands environment variables.

Important variables:

- `QDRANT_URL`
- `QDRANT_COLLECTION`
- `EMBEDDING_MODEL`
- `CHUNK_SIZE`
- `CHUNK_OVERLAP`
- `CHUNK_MANIFEST_PATH`
- `LLM_API_BASE_URL`
- `LLM_MODEL_NAME`
- `LLM_TIMEOUT_SECONDS`

Use `.env.example` as the template for local `.env`.

## Evaluation Dataset Format

JSON:

```json
[
  {
    "question": "How is the service deployed?",
    "ground_truth": "The service is deployed with Docker Compose.",
    "context": [
      "The service is deployed with Docker Compose. Start dependencies first."
    ]
  }
]
```

CSV columns:

```text
question,ground_truth,context
```

For multiple expected context snippets in CSV, separate them with `||`.

## Generated Files

Documentation RAG:

```text
data/chunks.jsonl
evaluation_results.json
final_audit_report.json
```

Repository Check:

```text
.repo-check/
  index/index.json
  project_brief.md
  security_audit.md
  findings.json
```

These outputs are ignored by git and can be regenerated.

## Tests

```bash
python -m pytest -q
```

Build package artifacts:

```bash
python -m build
```

## Limitations

- PDF and code-aware loaders are not implemented yet; ingestion currently targets Markdown and text.
- Repository Q&A uses a local lexical index, not the Qdrant pipeline.
- Security scanning is pattern-based and can produce false positives.
- RAGAS evaluation requires a reachable judge LLM.
- The optional web UI has no authentication; keep it local or behind your own access control.

## License

MIT
