# Second Brain for Devs + Repo Sentinel

Production-oriented local AI engineering playground with two connected parts:

- **Second Brain for Devs**: RAG pipeline for developer documentation using chunking, embeddings, Qdrant, retrieval, reranking, and evaluation.
- **Repo Sentinel**: local repository intelligence agent for onboarding, security audit, repository indexing, and Q&A through CLI or browser UI.

The project is packaged as a reusable Python module. After installation it exposes two console commands:

```bash
second-brain --help
repo-sentinel --help
```

Repo Sentinel is the newer agentic layer. It is designed to inspect repositories locally, generate useful reports, and avoid sending source code to cloud services by default.

## What Repo Sentinel Does

Repo Sentinel helps answer two practical questions after cloning or receiving a repository:

- **What is this project and how do I run it?**
- **Are there obvious local security risks before I spend cloud tokens or deploy anything?**

It provides:

- repository structure scanning;
- manifest parsing for Python, Node, Docker, docker-compose, and GitHub Actions;
- local lexical RAG index under `.reposentinel/index/`;
- Q&A over indexed repository files;
- secret pattern scanning with redacted evidence;
- risky script/config pattern scanning;
- Markdown reports for onboarding and security audit;
- JSON findings for later automation.

## Quick Start

Create a virtual environment and install the project:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[all]"
```

On Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"
```

Run Repo Sentinel against a repository:

```bash
repo-sentinel full C:\dev\some-repo
```

Ask a question about the repository:

```bash
repo-sentinel ask C:\dev\some-repo "How do I run this project locally?"
```

Use the document RAG toolkit:

```bash
docker compose up -d qdrant
second-brain doctor
second-brain ingest examples/example.md
second-brain ask "How is the Example Service deployed?"
```

## Web UI

Start the browser UI locally:

```bash
repo-sentinel web --host 127.0.0.1 --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

To run on a server and open from your main PC:

```bash
repo-sentinel web --host 0.0.0.0 --port 8765
```

Then open:

```text
http://SERVER_IP:8765
```

If the server firewall blocks inbound traffic, open TCP port `8765`.

The UI supports:

- `Index`;
- `Onboard`;
- `Audit`;
- `Full`;
- `Ask`;
- loading generated reports from `.reposentinel/`.

## CLI Commands

### Index

Build a local repository index:

```bash
repo-sentinel index C:\dev\some-repo
```

Output:

```text
C:\dev\some-repo\.reposentinel\index\index.json
```

### Onboard

Generate a project onboarding report:

```bash
repo-sentinel onboard C:\dev\some-repo
```

Output:

```text
C:\dev\some-repo\.reposentinel\project_brief.md
```

### Audit

Run local security scanners and generate a security report:

```bash
repo-sentinel audit C:\dev\some-repo
```

Output:

```text
C:\dev\some-repo\.reposentinel\security_audit.md
C:\dev\some-repo\.reposentinel\findings.json
```

### Full

Run indexing, onboarding, and security audit:

```bash
repo-sentinel full C:\dev\some-repo
```

### Ask

Ask a question using the local repository index:

```bash
repo-sentinel ask C:\dev\some-repo "Where is the application entrypoint?"
```

If the index is missing, run:

```bash
repo-sentinel index C:\dev\some-repo
```

You can force rebuild:

```bash
repo-sentinel ask C:\dev\some-repo "How do I run tests?" --force
```

## Generated Artifacts

Repo Sentinel writes local output into the inspected repository:

```text
.reposentinel/
  index/
    index.json
  project_brief.md
  security_audit.md
  findings.json
```

These files are safe to delete and regenerate.

Recommended `.gitignore` entry for target repositories:

```gitignore
.reposentinel/
```

## Architecture

Repo Sentinel is intentionally hybrid:

- deterministic tools collect facts;
- a LangGraph-compatible supervisor orchestrates workflow steps;
- local RAG provides repository memory;
- reports are generated from structured data.

High-level flow:

```text
CLI / Web UI
   ↓
Supervisor Graph
   ↓
Repo Scanner
Manifest Parser
Local RAG Indexer / Retriever
Secret Scanner
Script Risk Scanner
   ↓
Critic / Validation
   ↓
Markdown + JSON Reports
```

Current graph state includes:

- `messages`;
- `plan`;
- `iteration_count`;
- `error_log`;
- `root_path`;
- `mode`;
- `question`;
- `scan`;
- `profile`;
- `findings`;
- `retrieved_context`;
- `reports`;
- `status`.

The graph has a hard iteration limit to avoid runaway loops.

## Tools

Repo Sentinel tools are async and Pydantic-validated.

Implemented tools:

- `file_manager`: safe file read/write/list/delete inside a root path;
- `repo_scanner`: deterministic repository file and directory scan;
- `manifest_parser`: extracts languages, package managers, scripts, dependencies, and commands;
- `secret_scanner`: scans for common secrets and redacts evidence;
- `script_risk_scanner`: detects risky shell, Docker, CI, and config patterns;
- `rag_indexer`: builds a local text index;
- `rag_retriever`: performs local lexical retrieval.

The scanners are deliberately boring and deterministic. The agentic layer should reason over facts, not invent facts.

## Security Scanner Coverage

The current security audit checks for:

- AWS-style access keys;
- GitHub tokens;
- Slack tokens;
- private key headers;
- generic `api_key`, `secret`, `token`, and `password` assignments;
- `curl | sh`;
- `wget | bash`;
- `rm -rf`;
- `chmod 777`;
- `sudo`;
- `eval`;
- PowerShell `Invoke-Expression`;
- `Set-ExecutionPolicy Bypass`;
- Docker `--privileged`;
- Docker socket mounts.

This is not a replacement for a full SAST/DAST/security review. It is a fast local pre-check.

## Local RAG

Repo Sentinel's local RAG does not require Qdrant or external APIs.

It:

- skips noisy directories such as `.git`, `.venv`, `node_modules`, `dist`, `build`, `__pycache__`, `.pytest_cache`, and `.reposentinel/index`;
- chunks text files;
- writes a JSON index;
- uses BM25 if `rank-bm25` is installed;
- falls back to token-overlap scoring.

This is enough for repository Q&A and report context without spending cloud tokens.

## Second Brain RAG

The original Second Brain pipeline is still available.

Start Qdrant:

```bash
docker compose up -d qdrant
```

Ingest a Markdown or text document:

```bash
second-brain ingest path/to/document.md
```

Unified CLI for the original RAG workflow:

```bash
second-brain status
second-brain doctor
second-brain ingest path/to/document.md
second-brain ask "What is this document about?"
```

## Library Usage

```python
from second_brain.app import build_orchestrator
from second_brain.config import load_config
from second_brain.ingestion.pipeline import IngestionPipeline

config = load_config("config/default.yaml")
IngestionPipeline(config).ingest_file("examples/example.md")
response = build_orchestrator(config).answer("How is the service deployed?")

print(response.answer)
```

## Project Structure

```text
src/
  second_brain/
    ingestion/           # Document schemas, chunking, embeddings, Qdrant upload
    retrieval/           # Hybrid retrieval, reranking, vector store abstractions
    orchestration/       # RAG orchestration and LLM client
    evaluation/          # RAG evaluation helpers
    repo_intel/
      cli.py             # Repo Sentinel CLI
      graph.py           # LangGraph-compatible supervisor
      state.py           # AgentState
      web.py             # FastAPI browser UI
      rag/               # Local repository indexer/retriever
      reports/           # Markdown/JSON report generation
      tools/             # Deterministic async tools and scanners
tests/
  test_repo_intel_*.py
```

## Development

Run tests:

```bash
python -m pytest -q
```

Compile-check the Repo Sentinel package:

```bash
python -m compileall -q src\second_brain\repo_intel main.py
```

Run the full Repo Sentinel workflow against this repository:

```bash
repo-sentinel full C:\dev\seniorAIeng
```

## Current Limitations

- `ask` currently uses local lexical retrieval, not embeddings.
- Security scanning is pattern-based and can produce false positives.
- The web UI runs tasks request-by-request and does not yet stream logs.
- There is no authentication on the web UI yet. Do not expose it directly to the public internet.
- Destructive tool actions should stay behind an approval gate before adding them to the UI.

## Suggested Next Steps

- Add authenticated web access for server use.
- Add streaming run logs in the UI.
- Add job history under `.reposentinel/runs/`.
- Add optional embedding-based retrieval with a local model.
- Add dependency audit integration with explicit approval for network calls.
- Add Docker and CI-specific scanners as separate modules.
