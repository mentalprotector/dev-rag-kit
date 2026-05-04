# Using Dev RAG Kit as a Reusable Module

`dev-rag-kit` can be used in two ways:

- as a CLI toolkit for document RAG and repository analysis;
- as a Python library embedded into another project.

## Install

Minimal RAG install:

```bash
pip install -e .
```

Full local development install:

```bash
pip install -e ".[all]"
```

Evaluation-only extras:

```bash
pip install -e ".[eval]"
```

Web UI extras:

```bash
pip install -e ".[web]"
```

## CLI

Document RAG:

```bash
dev-rag status
dev-rag doctor
dev-rag ingest docs/example.md
dev-rag ask "What does this document say about deployment?"
dev-rag chat
dev-rag evaluate config/gold_standard.example.json --output evaluation_results.json
```

Full E2E run:

```bash
dev-rag e2e \
  --document docs/example.md \
  --question "What is the deployment flow?" \
  --dataset config/gold_standard.example.json \
  --output final_audit_report.json
```

Repository intelligence:

```bash
repo-check full /path/to/repo
repo-check ask /path/to/repo "How do I run this project?"
repo-check web --host 127.0.0.1 --port 8765
```

## Library API

```python
from dev_rag.config import load_config
from dev_rag.ingestion.pipeline import IngestionPipeline
from dev_rag.app import build_orchestrator

config = load_config("config/default.yaml")

uploaded = IngestionPipeline(config).ingest_file("docs/example.md")
orchestrator = build_orchestrator(config)
response = orchestrator.answer("What is this document about?")

print(uploaded)
print(response.answer)
```

## Required Services

Qdrant:

```bash
docker compose up -d qdrant
```

LM Studio must expose an OpenAI-compatible API. Configure:

```env
LLM_API_BASE_URL=http://YOUR_LM_STUDIO_HOST:1234/v1
LLM_MODEL_NAME=unsloth/gemma-4-26b-a4b-it
```

Run:

```bash
dev-rag doctor
```

before an E2E test.
