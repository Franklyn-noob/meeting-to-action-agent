# Meeting-to-Action Agent

> A **Strands Agents SDK** agent deployed on **Amazon Bedrock AgentCore** that
> turns meeting transcripts into tracked action items, drafts follow-up email,
> and **only interrupts you when a task is overdue or ownership is ambiguous.**
> Everything else is handled silently. Built for AWS's "Agents for Humans"
> hackathon (Professional Agents track).

## What it does

1. **Ingests** a meeting transcript (plain text).
2. **Extracts** structured action items → task, owner, due date, and an
   *ownership confidence* score (so ambiguity is detectable).
3. **Creates** a task record per item and **drafts** a recap / follow-up email.
4. **Persists state** across sessions so open tasks can be tracked.
5. **Daily background check** that escalates to the user **only** when a task is
   (a) overdue, or (b) ambiguously-owned — everything else stays silent.
6. **Logs activity** with a distinct `auto-handled` vs `escalation` signal so the
   dashboard can clearly show "running quietly" vs "needs your input".

## Demo (works fully offline, no AWS credentials required)

The repository ships with a deterministic offline mode so you can run the **entire
system** without an LLM backend or AWS account:

```bash
./run_demo.sh
# then open http://127.0.0.1:8000
```

In offline mode (`MODEL_PROVIDER=fake`) three sample meetings are seeded
automatically and processed through the agent pipeline using a `FakeLLM` with
canned responses — including one **overdue** task and one **ambiguous-owner**
task, both surfaced as escalations. No Ollama, no AWS needed.

To use a **real local model** (Ollama), start Ollama and run:

```bash
MODEL_PROVIDER=local ./run_demo.sh   # ensure `ollama run llama3.3` is available
```

To use **Bedrock** (deploy), set `MODEL_PROVIDER=bedrock` and provide AWS
credentials (see the Deploy section).

## Local setup (manual)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
npm run build --prefix frontend          # build the dashboard once (or `npm run dev --prefix frontend`)
uvicorn backend.api:app --host 127.0.0.1 --port 8000
# open http://127.0.0.1:8000
```

## Testing

```bash
. .venv/bin/activate            # if not already
pytest
```

The suite is fully offline: a `FakeLLM` returns deterministic structured JSON and
a `LocalJsonStore` backs state with temp files. It covers schema
serialization, store round-trips, extraction/ambiguity logic, the full pipeline
on each sample transcript, escalation idempotency, and the FastAPI endpoints.

## API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/process-transcript` | `{"transcript","source"}` → run pipeline |
| `POST` | `/api/demo/seed` | Re-seed the 3 sample meetings |
| `POST` | `/api/run-daily-check` | Trigger the background escalation check |
| `POST` | `/api/tasks/{id}/done` | Mark a task complete |
| `GET`  | `/api/state` | Tasks grouped by status + counts |
| `GET`  | `/api/tasks` | All tasks |
| `GET`  | `/api/escalations` | Surfacing escalations only |
| `GET`  | `/api/activity` | Full chronological activity log |
| `GET`  | `/api/activity/sse` | Live SSE of the activity log (`?once=true` = single snapshot) |
| `GET`  | `/api/config` | Runtime config (provider, persistence, email) |

## Architecture (see [architecture.md](architecture.md) for details)

- `meeting_agent/tools/` — four Strands `@tool` modules (extraction, task
  tracking, email drafting, escalation check) + `current_time` + `markTaskDone`.
  Each has a **pure core** (testable, takes an explicit `llm`/`store`) and a
  `@tool` wrapper (what the Strands `Agent` calls).
- `meeting_agent/llm.py` — model abstraction: `FakeLLM` (tests), `OpenAILLM`
  (local/Ollama), `BedrockLLM` (deploy). Env-driven via `MODEL_PROVIDER`.
- `meeting_agent/store.py` — `TaskStore` abstraction with `LocalJsonStore`
  (local/offline) and `AgentCoreMemoryStore` (deploy phase).
- `meeting_agent/orchestrator.py` — the end-to-end pipeline used by the backend
  and local demo (offline-friendly).
- `meeting_agent/agent.py` — the **Strands `Agent`** + `BedrockAgentCoreApp`
  entrypoint used by the deployed runtime.
- `backend/api.py` — FastAPI app: JSON + SSE endpoints and the SPA static mount.
- `frontend/` — React + Vite + Tailwind single-page dashboard.

## Deploy to Amazon Bedrock AgentCore (separate phase)

> Requires AWS credentials with permissions to create AgentCore runtimes, IAM
> roles, and (optionally) Secrets Manager. Local demo does **not** need this.

1. Install the AgentCore CLI:
   `pip install bedrock-agentcore[aoc]` then `pip install --force-reinstall --no-deps amazon-bedrock-agentcore-cli` (or `brew install aws/bedrock-agentcore/agentcore`).
2. Configure AWS (`aws configure`) and set the region: `export AWS_REGION=us-east-1`.
3. Build a deployment configuration and deploy:
   ```bash
   MODEL_PROVIDER=bedrock AGENTCORE_DEPLOY=1 agentcore deploy
   ```
4. On first run, create the AgentCore Memory namespace used by
   `AgentCoreMemoryStore` (the `create_or_get_memory(...)` call in
   `store.py`) and grant the runtime's execution role permission to call
   `memory` and `bedrock:Converse`.
5. For email sending in production, set `EMAIL_SENDER=ses` and store SMTP/SES
   credentials in **AWS Secrets Manager** (never in code).

The agent is wrapped in `BedrockAgentCoreApp` and exposed via `app.run()` — see
`meeting_agent/agent.py` (`handler` entrypoint).

## Built-in tools (strands-agents-tools 1.54)

Strands ships its built-in tools via the **`strands-agents-tools`** package on
PyPI, imported as `strands_tools` (e.g. `from strands_tools.current_time import
current_time`). This is the package that provides `current_time` / `http_request`
/ `shell` / `sleep`; the standalone `strands-tools` name on PyPI does **not**
exist, which is why some older examples 404. We import the real `current_time`
tool directly (`meeting_agent/tools/current_time.py` re-exports it and routes
the pipeline's `now()` through it). Note: `current_time` is deprecated upstream
in favour of the [ContextInjector](https://strandsagents.com/docs/user-guide/concepts/plugins/context-injector/)
plugin, but is fully functional today; its deprecation chatter is silenced so
local runs stay clean.

## License

MIT — see [LICENSE](LICENSE).
