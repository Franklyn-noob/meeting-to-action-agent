"""FastAPI backend for the Meeting-to-Action Agent.

Exposes the agent's state to the dashboard:
  POST /api/process-transcript  — run the extract->create->email->check pipeline
  POST /api/demo/seed           — process all sample transcripts (offline demo)
  POST /api/run-daily-check     — trigger the background escalation check
  POST /api/tasks/{id}/done     — mark a task complete
  GET  /api/state               — tasks grouped by status + activity feed
  GET  /api/tasks               — all tasks
  GET  /api/escalations         — surfaced escalations only
  GET  /api/activity            — full chronological activity log
  GET  /api/activity/sse        — SSE stream of the activity log
  GET  /api/config              — runtime config (provider, counts)
  GET  /                        — served from frontend/dist (SPA) if built

In ``MODEL_PROVIDER=fake`` the backend runs fully offline using deterministic
demo fixtures (see ``meeting_agent.sample_data``); otherwise it uses the
configured LLM (Ollama local / Bedrock deploy).
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from meeting_agent.orchestrator import list_state, process_transcript
from meeting_agent.schemas import ActivityKind, TaskStatus
from meeting_agent.scheduler import run_daily_check
from meeting_agent.store import get_store
from meeting_agent.tools.mark_done import mark_task_done

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = ROOT / "frontend" / "dist"

app = FastAPI(title="Meeting-to-Action Agent", docs_url="/api/docs")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start up: in offline/demo mode, pre-process the sample transcripts."""
    provider = os.getenv("MODEL_PROVIDER", "local").lower()
    if provider == "fake":
        store = get_store()
        if not store.list_tasks():
            from meeting_agent.sample_data import SEED_TRANSCRIPTS
            import logging

            log = logging.getLogger("backend")
            for source, transcript in SEED_TRANSCRIPTS.items():
                try:
                    process_transcript(transcript, source=source)
                except Exception as exc:  # pragma: no cover - demo path
                    log.warning("Demo seed failed for %s: %s", source, exc)
    yield


app = FastAPI(title="Meeting-to-Action Agent", docs_url="/api/docs", lifespan=lifespan)


class ProcessTranscriptIn(BaseModel):
    transcript: str
    source: str = "transcript"


@app.post("/api/process-transcript")
def process_transcript_endpoint(payload: ProcessTranscriptIn) -> dict:
    result = process_transcript(payload.transcript, source=payload.source)
    email = None
    if result.email:
        email = {"to": result.email.to, "subject": result.email.subject, "body": result.email.body}
    return {
        "tasks": [t.model_dump(mode="json") for t in result.tasks],
        "escalations": [e.model_dump(mode="json") for e in result.escalations],
        "email": email,
        "activity": [a.model_dump(mode="json") for a in result.activity],
    }


@app.post("/api/demo/seed")
def demo_seed() -> dict:
    """Re-process all sample transcripts (useful to reset the demo)."""
    store = get_store()
    from meeting_agent.sample_data import SEED_TRANSCRIPTS

    results = []
    for source, transcript in SEED_TRANSCRIPTS.items():
        r = process_transcript(transcript, source=source)
        results.append(
            {
                "source": source,
                "tasks": len(r.tasks),
                "escalations": len(r.escalations),
            }
        )
    return {"seeded": results}


@app.post("/api/run-daily-check")
def run_daily_check_endpoint() -> dict:
    escalations = run_daily_check(force=True)
    return {
        "escalations": [e.model_dump(mode="json") for e in escalations],
        "count": len(escalations),
    }


@app.post("/api/tasks/{task_id}/done")
def mark_done(task_id: str) -> dict:
    ok = mark_task_done(task_id, store=get_store())
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "task not found"})
    return {"done": ok, "task_id": task_id}


@app.get("/api/state")
def state() -> dict:
    """Dashboard initial load: tasks grouped by status + full activity feed."""
    data = list_state(get_store())
    by_status: dict[str, list] = {s.value: [] for s in TaskStatus}
    for t in data["tasks"]:
        by_status.setdefault(t["status"], []).append(t)
    return {
        "tasks_by_status": by_status,
        "activity": data["activity"],
        "counts": {
            "total_tasks": len(data["tasks"]),
            "escalations": sum(1 for a in data["activity"] if a["kind"] == ActivityKind.ESCALATION.value),
        },
    }


@app.get("/api/tasks")
def tasks() -> list:
    store = get_store()
    return [t.model_dump(mode="json") for t in store.list_tasks()]


@app.get("/api/escalations")
def escalations() -> list:
    store = get_store()
    return [
        a.model_dump(mode="json")
        for a in store.activity_feed()
        if a.kind == ActivityKind.ESCALATION
    ]


@app.get("/api/activity")
def activity() -> list:
    store = get_store()
    return [a.model_dump(mode="json") for a in store.activity_feed()]


@app.get("/api/activity/sse")
async def activity_sse(once: bool = False):
    """Server-Sent Events feed of the activity log.

    Re-pushes the current feed periodically. Pass ``?once=true`` to receive a
    single snapshot and disconnect (used by tests / initial dashboard load).
    """

    def event(data: str) -> str:
        return f"data: {data}\n\n"

    async def generator():
        store = get_store()
        sent = 0
        while True:
            feed = [a.model_dump(mode="json") for a in store.activity_feed()]
            if len(feed) != sent:
                yield event(json.dumps({"type": "snapshot", "data": feed}))
                sent = len(feed)
            if once:
                return
            await asyncio.sleep(2)

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.get("/api/config")
def config() -> dict:
    return {
        "model_provider": os.getenv("MODEL_PROVIDER", "local"),
        "persistence": os.getenv("PERSISTENCE", "local"),
        "email_sender": os.getenv("EMAIL_SENDER", "simulated"),
    }


# Serve the built SPA if present (built by `npm run build` in frontend/).
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
else:
    @app.get("/")
    def root() -> HTMLResponse:
        return HTMLResponse(
            """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Meeting-to-Action Agent</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:sans-serif;max-width:640px;margin:3rem auto;padding:0 1rem;color:#e2e8f0;background:#0f172a}
a{color:#38bdf8}code{background:#1e293b;padding:.1rem .35rem;border-radius:4px}</style>
</head><body>
<h1>Meeting-to-Action Agent</h1>
<p>The dashboard is not built yet. Build it first, then reload:</p>
<pre><code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code></pre>
<p>Or just run the demo: <code>./run_demo.sh</code></p>
</body></html>"""
        )
