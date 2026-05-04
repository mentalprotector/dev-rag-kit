# Using Second Brain for Devs as a Reusable Module

`second-brain-for-devs` can be used in two ways:

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
second-brain status
second-brain doctor
second-brain ingest docs/example.md
second-brain ask "What does this document say about deployment?"
second-brain chat
second-brain evaluate config/gold_standard.example.json --output evaluation_results.json
```

Full E2E run:

```bash
second-brain e2e \
  --document docs/example.md \
  --question "What is the deployment flow?" \
  --dataset config/gold_standard.example.json \
  --output final_audit_report.json
```

Repository intelligence:

```bash
repo-sentinel full /path/to/repo
repo-sentinel ask /path/to/repo "How do I run this project?"
repo-sentinel web --host 127.0.0.1 --port 8765
```

## Library API

```python
from second_brain.config import load_config
from second_brain.ingestion.pipeline import IngestionPipeline
from second_brain.app import build_orchestrator

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
LLM_MODEL_NAME=google/gemma-4-26b-a4b
```

Run:

```bash
second-brain doctor
```

before an E2E test.
