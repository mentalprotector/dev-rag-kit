"""FastAPI web UI for Repo Check."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from dev_rag.repo_intel.graph import run_repo_intel

Mode = Literal["index", "onboard", "audit", "full", "ask"]


class RunRequest(BaseModel):
    """Request payload for running a repository workflow."""

    mode: Mode
    root_path: str = Field(min_length=1)
    question: str | None = None
    force: bool = False


class ReportRequest(BaseModel):
    """Request payload for reading generated report artifacts."""

    root_path: str = Field(min_length=1)


def create_app() -> Any:
    """Create the Repo Check web app."""

    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import HTMLResponse
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Web UI requires fastapi and uvicorn. Install with: pip install fastapi uvicorn"
        ) from exc

    app = FastAPI(title="Repo Check", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return _html()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/run")
    async def run(request: RunRequest) -> dict[str, object]:
        root = Path(request.root_path).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise HTTPException(status_code=400, detail=f"Repository path does not exist: {root}")
        if request.mode == "ask" and not (request.question or "").strip():
            raise HTTPException(status_code=400, detail="Question is required for ask mode")
        return await run_repo_intel(
            mode=request.mode,
            root_path=root,
            question=request.question,
            force_rebuild=request.force,
        )

    @app.post("/api/reports")
    async def reports(request: ReportRequest) -> dict[str, str]:
        root = Path(request.root_path).expanduser().resolve()
        output_dir = root / ".repo-check"
        files = {
            "project_brief": output_dir / "project_brief.md",
            "security_audit": output_dir / "security_audit.md",
            "findings_json": output_dir / "findings.json",
        }
        return {
            name: path.read_text(encoding="utf-8") if path.exists() else ""
            for name, path in files.items()
        }

    return app


def run_web(host: str, port: int) -> None:
    """Run the web server."""

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Web UI requires uvicorn. Install with: pip install fastapi uvicorn") from exc
    uvicorn.run(create_app(), host=host, port=port)


def _html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Repo Check</title>
  <style>
    :root {
      --ink: #17211b;
      --muted: #637168;
      --paper: #f6f0df;
      --card: #fffaf0;
      --line: #1f2b22;
      --accent: #e85d2a;
      --accent-2: #245c4f;
      --soft: #eadfbe;
      --shadow: 10px 10px 0 #17211b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(circle at 12% 20%, rgba(232,93,42,.18), transparent 28rem),
        radial-gradient(circle at 84% 0%, rgba(36,92,79,.20), transparent 24rem),
        linear-gradient(135deg, #f7efd7 0%, #efe2bd 100%);
      min-height: 100vh;
    }
    .shell { width: min(1180px, calc(100vw - 32px)); margin: 28px auto 48px; }
    header { display: grid; grid-template-columns: 1.1fr .9fr; gap: 20px; margin-bottom: 20px; }
    .hero, .panel {
      border: 2px solid var(--line);
      background: rgba(255,250,240,.9);
      box-shadow: var(--shadow);
    }
    .hero { padding: 30px; position: relative; overflow: hidden; }
    .hero:after {
      content: ""; position: absolute; right: -58px; top: -58px; width: 190px; height: 190px;
      border: 2px solid var(--line);
      background: repeating-linear-gradient(45deg, #245c4f, #245c4f 12px, #f6f0df 12px, #f6f0df 24px);
      transform: rotate(12deg);
    }
    .eyebrow {
      font: 700 12px/1.2 ui-monospace, SFMono-Regular, Consolas, monospace;
      letter-spacing: .14em; text-transform: uppercase; color: var(--accent-2);
    }
    h1 { font-size: clamp(42px, 7vw, 82px); line-height: .86; letter-spacing: -.06em; margin: 18px 0; }
    .hero p { max-width: 680px; color: var(--muted); font-size: 18px; line-height: 1.45; margin: 0; }
    .panel { padding: 22px; }
    label {
      display: block; font: 700 12px/1.2 ui-monospace, SFMono-Regular, Consolas, monospace;
      text-transform: uppercase; letter-spacing: .08em; margin: 0 0 8px;
    }
    input, textarea {
      width: 100%; border: 2px solid var(--line); background: #fffdf6; color: var(--ink);
      font: 15px/1.4 ui-monospace, SFMono-Regular, Consolas, monospace; padding: 12px; outline: none;
    }
    textarea { min-height: 86px; resize: vertical; }
    .field { margin-bottom: 14px; }
    .grid { display: grid; grid-template-columns: 360px 1fr; gap: 20px; align-items: start; }
    .buttons { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 16px; }
    button {
      border: 2px solid var(--line); background: var(--accent); color: #fffaf0; padding: 12px 14px;
      font: 800 13px/1 ui-monospace, SFMono-Regular, Consolas, monospace; text-transform: uppercase;
      cursor: pointer; box-shadow: 4px 4px 0 var(--line); transition: transform .12s ease, box-shadow .12s ease;
    }
    button.secondary { background: var(--accent-2); }
    button:hover { transform: translate(-2px, -2px); box-shadow: 6px 6px 0 var(--line); }
    button:disabled { opacity: .55; cursor: wait; transform: none; }
    .status {
      display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 14px;
      padding: 12px; border: 2px solid var(--line); background: var(--soft);
      font: 700 13px/1.3 ui-monospace, SFMono-Regular, Consolas, monospace;
    }
    .pill { border: 2px solid var(--line); padding: 6px 10px; background: #fffaf0; white-space: nowrap; }
    .tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
    .tab { background: #fffaf0; color: var(--ink); box-shadow: none; padding: 9px 10px; }
    .tab.active { background: var(--accent-2); color: #fffaf0; }
    pre {
      margin: 0; min-height: 460px; max-height: 68vh; overflow: auto; white-space: pre-wrap; word-break: break-word;
      border: 2px solid var(--line); background: #101712; color: #edf7df; padding: 16px;
      font: 13px/1.55 ui-monospace, SFMono-Regular, Consolas, monospace;
    }
    .hint { color: var(--muted); font-size: 14px; line-height: 1.45; margin-top: 14px; }
    code { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
    @media (max-width: 880px) {
      header, .grid { grid-template-columns: 1fr; }
      .buttons { grid-template-columns: 1fr; }
      .hero:after { opacity: .25; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <section class="hero">
        <div class="eyebrow">Local Repository Intelligence</div>
        <h1>Repo Check</h1>
        <p>Run onboarding, local security audit, indexing, and RAG Q&A from a browser while the code stays on your server.</p>
      </section>
      <section class="panel">
        <div class="field">
          <label for="rootPath">Repository path on server</label>
          <input id="rootPath" value="C:\\dev\\seniorAIeng" />
        </div>
        <div class="field">
          <label for="question">Ask mode question</label>
          <textarea id="question">Как запустить этот проект?</textarea>
        </div>
        <label><input id="force" type="checkbox" style="width:auto;margin-right:8px;"> Force rebuild index</label>
        <div class="buttons">
          <button data-mode="index">Index</button>
          <button data-mode="onboard" class="secondary">Onboard</button>
          <button data-mode="audit" class="secondary">Audit</button>
          <button data-mode="full">Full</button>
          <button data-mode="ask">Ask</button>
          <button id="loadReports" class="secondary">Load Reports</button>
        </div>
        <p class="hint">LAN: <code>python main.py web --host 0.0.0.0 --port 8765</code>, then open <code>http://server-ip:8765</code>.</p>
      </section>
    </header>

    <section class="grid">
      <aside class="panel">
        <div class="status">
          <span id="statusText">Idle</span>
          <span class="pill" id="duration">0 ms</span>
        </div>
        <div class="hint">Reports are written to <code>.repo-check/</code>. The UI calls the same runner as the CLI.</div>
      </aside>
      <section class="panel">
        <div class="tabs">
          <button class="tab active" data-tab="result">Result</button>
          <button class="tab" data-tab="project_brief">Project Brief</button>
          <button class="tab" data-tab="security_audit">Security Audit</button>
          <button class="tab" data-tab="findings_json">Findings JSON</button>
        </div>
        <pre id="output">Ready.</pre>
      </section>
    </section>
  </main>

  <script>
    const output = document.querySelector("#output");
    const statusText = document.querySelector("#statusText");
    const duration = document.querySelector("#duration");
    const tabs = document.querySelectorAll(".tab");
    let buffers = { result: "Ready.", project_brief: "", security_audit: "", findings_json: "" };

    function setActive(tab) {
      tabs.forEach(el => el.classList.toggle("active", el.dataset.tab === tab));
      output.textContent = buffers[tab] || "No content yet.";
    }

    async function postJson(url, payload) {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || JSON.stringify(data));
      return data;
    }

    async function runMode(mode) {
      const started = performance.now();
      statusText.textContent = `Running ${mode}...`;
      document.querySelectorAll("button").forEach(button => button.disabled = true);
      try {
        const payload = {
          mode,
          root_path: document.querySelector("#rootPath").value,
          question: document.querySelector("#question").value,
          force: document.querySelector("#force").checked
        };
        const data = await postJson("/api/run", payload);
        buffers.result = JSON.stringify(data, null, 2);
        if (data.answer) buffers.result += `\\n\\n${data.answer}`;
        setActive("result");
        statusText.textContent = data.status === "ok" ? "Completed" : "Finished with errors";
        if (["onboard", "audit", "full"].includes(mode)) await loadReports(false);
      } catch (error) {
        buffers.result = `Error: ${error.message}`;
        setActive("result");
        statusText.textContent = "Error";
      } finally {
        duration.textContent = `${Math.round(performance.now() - started)} ms`;
        document.querySelectorAll("button").forEach(button => button.disabled = false);
      }
    }

    async function loadReports(switchTab = true) {
      const data = await postJson("/api/reports", { root_path: document.querySelector("#rootPath").value });
      buffers = { ...buffers, ...data };
      if (switchTab) setActive("project_brief");
    }

    document.querySelectorAll("button[data-mode]").forEach(button => {
      button.addEventListener("click", () => runMode(button.dataset.mode));
    });
    document.querySelector("#loadReports").addEventListener("click", () => loadReports(true));
    tabs.forEach(tab => tab.addEventListener("click", () => setActive(tab.dataset.tab)));
  </script>
</body>
</html>"""
