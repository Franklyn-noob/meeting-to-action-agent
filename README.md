# Meeting-to-Action Agent

> A **Strands Agents SDK** agent deployed on **Amazon Bedrock AgentCore** that
> turns meeting transcripts into tracked action items, drafts a follow-up email,
> and **only interrupts you when a task is overdue or ownership is ambiguous.**
> Everything else is handled silently.
>
> Built for AWS's **Agents for Humans** hackathon — Professional Agents track.

---

## What it does

Professionals lose hours every week manually pulling action items out of meeting
notes and then chasing people down for follow-through. This agent automates the
whole loop end-to-end and only surfaces a notification when a **real decision is
needed**:

1. **Ingests** a meeting transcript (plain text — e.g. a Zoom/Meet export).
2. **Extracts** structured action items → task description, owner name, and any
   stated or implied due date, plus an *ownership confidence* score (so
   ambiguity is detectable, not just missing data).
3. **Creates** a task record per item and **drafts** a recap / follow-up email
   that assigns owners and summarizes decisions.
4. **Persists state** across sessions so open tasks can be tracked to completion.
5. **Background daily check** that escalates to the user **only** when a task is
   (a) overdue, or (b) ambiguously owned — everything else is handled silently.
6. **Logs activity** with a distinct `auto-handled` vs `escalation` signal so the
   dashboard can clearly show "running quietly" vs "needs your input."

## Quick start (fully offline, no AWS / LLM key required)

```bash
./run_demo.sh
# then open http://127.0.0.1:8000
```

In the default offline mode (`MODEL_PROVIDER=fake`) three sample meetings are
seeded automatically and processed through the full agent pipeline using a
`FakeLLM` with deterministic canned responses — including one **overdue** task
and one **ambiguous-owner** task, both surfaced as escalations.

## Architecture overview

- **`meeting_agent/`** — the Strands agent + pipeline.
  - `agent.py` — the **Strands `Agent`** + `BedrockAgentCoreApp` entrypoint used
    by the deployed runtime (`handler`).
  - `orchestrator.py` — the end-to-end pipeline (extraction → task creation →
    email drafting → background escalation check); shared by the backend and the
    local demo. Offline-friendly.
  - `store.py` — `TaskStore` abstraction: `LocalJsonStore` (local/offline) and
    `AgentCoreMemoryStore` (deploy phase).
  - `llm.py` — model abstraction driven by `MODEL_PROVIDER`:
    `FakeLLM` (tests/offline), `OpenAILLM` (local/Ollama), `GroqLLM` (real
    hosted model), `BedrockLLM` (deploy).
  - `tools/` — Strands `@tool` modules, each with a **pure core** (testable,
    takes an explicit `llm`/`store`) and a `@tool` wrapper (what the Strands
    `Agent` calls):
    1. `extract_action_items` — structured JSON extraction with ownership
       confidence.
    2. `create_task` — persist a task record.
    3. `draft_followup_email` — compose a recap/follow-up email.
    4. `check_overdue_and_escalate` — background overdue/ambiguous sweep.
    (+ `current_time` re-exported from `strands-agents-tools`, and `markTaskDone`.)
  - `schemas.py` — pydantic models (Task, ActionItem, EscalationReason, …).
- **`backend/api.py`** — FastAPI app: JSON + SSE endpoints and the SPA static
  mount. Single process (`./run_demo.sh` starts uvicorn on `:8000`).
- **`frontend/`** — React 18 + Vite 5 + Tailwind CSS single-page dashboard
  (task board, meetings feed, activity log with auto-handled vs escalation view).
- **Deployment target** — **Amazon Bedrock AgentCore** Runtime (container,
  `us-east-1`), via `BedrockAgentCoreApp` (`agent.py`).

## Tech stack

| Layer | Tech |
| --- | --- |
| Agent runtime | [Strands Agents SDK](https://github.com/strands-agents) (`strands-agents`, `strands-agents-tools`) |
| Orchestration backend | FastAPI + uvicorn |
| Frontend | React 18, Vite 5, Tailwind CSS 3 |
| Model providers | `FakeLLM` (offline), OpenAI-compat (Ollama), **Groq**, **Bedrock** (Anthropic) |
| Cloud / deploy | AWS Bedrock AgentCore, ECR, IAM, (optional SES) |
| Persistence | local JSON (offline) → AgentCore Memory (deploy) |
| Email | `smtplib` SMTP (Gmail) / Amazon SES / simulated |

## Setup

**Prerequisites**
- Python **3.10+** (developed on 3.12)
- Node **20+** (frontend build)
- `git`

```bash
git clone <repo-url>
cd meeting-to-action-agent

# Python backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt          # or: pip install -e ".[dev]"  (pulls pytest)

# Frontend (build once; the API serves the built SPA)
cd frontend && npm install && npm run build && cd ..
```

The demo script `./run_demo.sh` will also create the venv, install deps, and build
the frontend for you — it's the fastest way to get running.

## Environment variables

Secrets are loaded from `./groq.env` (local/demo) and never committed — see
`.gitignore`. Production injects the same names via the runtime / Secrets
Manager.

**Model (`MODEL_PROVIDER`)** — controls which LLM powers the agent:

| Value | Provider | What it needs |
| --- | --- | --- |
| `fake` *(default)* | `FakeLLM` | nothing — deterministic offline demo |
| `local` | OpenAI-compatible (Ollama) | Ollama running + a model (e.g. `ollama run llama3.3`) |
| `groq` | `GroqLLM` | `groq_api` / `GROQ_API_KEY` in `groq.env` (or env); optional `GROQ_MODEL_ID` |
| `bedrock` | `BedrockLLM` | AWS creds + a model enabled in your account (see Status) |

**Email (`EMAIL_PROVIDER` / `EMAIL_SENDER`)** — controls how follow-up emails are
sent (the email step is the same pipeline either way):

| Option | Sender | What it needs |
| --- | --- | --- |
| *(unset)* — default | `SimulatedEmailSender` | nothing — logs only, fully offline |
| `EMAIL_PROVIDER=smtp` | `SmtpEmailSender` (real Gmail SMTP) | `smtp_email` + `smtp_password` (Gmail **app password**) in `groq.env` |
| `EMAIL_SENDER=ses` | `SesEmailSender` (Amazon SES) | AWS creds (deploy only) |

## Running locally

```bash
./run_demo.sh                              # offline demo (MODEL_PROVIDER=fake)
MODEL_PROVIDER=local  ./run_demo.sh        # real local model via Ollama
MODEL_PROVIDER=groq   ./run_demo.sh        # real Groq model
EMAIL_PROVIDER=smtp   ./run_demo.sh        # ...and real Gmail SMTP email
MODEL_PROVIDER=groq EMAIL_PROVIDER=smtp ./run_demo.sh   # both, live
```

`run_demo.sh` boots the FastAPI backend (which serves the built React dashboard)
on `http://127.0.0.1:8000`. It only loads local secrets from `groq.env` when a
provider actually needs them (`groq`/`smtp`); otherwise it never touches the file.

### API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/process-transcript` | `{"transcript","source"}` → run the pipeline |
| `POST` | `/api/demo/seed` | Re-seed the 3 sample meetings |
| `POST` | `/api/run-daily-check` | Trigger the background escalation check |
| `POST` | `/api/tasks/{id}/done` | Mark a task complete |
| `GET`  | `/api/config` | Runtime config (provider, persistence, email) |
| `GET`  | `/api/state` | Tasks grouped by status + counts |
| `GET`  | `/api/tasks` | All tasks |
| `GET`  | `/api/escalations` | Surfacing escalations only |
| `GET`  | `/api/activity` | Full chronological activity log |
| `GET`  | `/api/activity/sse` | Live SSE feed (`?once=true` = single snapshot) |

## Testing

```bash
. .venv/bin/activate     # if not already active
pytest                   # or: python -m pytest -q
```

The suite is fully **offline**: a `FakeLLM` returns deterministic structured JSON
and a `LocalJsonStore` backs state with temp files. It covers schema
serialization, store round-trips, extraction/ambiguity logic, the full pipeline on
each sample transcript, escalation idempotency, and the FastAPI endpoints.

## Deploying to Amazon Bedrock AgentCore

> Requires AWS credentials with permissions to create AgentCore runtimes, IAM
> roles/ECR. The **local** demo does **not** need any of this.

1. Install the AgentCore Starter Kit:
   `pip install bedrock-agentcore-starter-toolkit` (the `agentcore` CLI this
   project is built on — **not** `bedrock-agentcore[aoc]` / `@aws/agentcore`).
2. Configure AWS and set the region: `aws configure` then `export AWS_REGION=us-east-1`.
3. Configure & deploy (this project's actual two-step flow):
   ```bash
   # 1) Configure the AgentCore runtime: container packaging + ECR repo + IAM role
   agentcore configure --create \
     --name meeting_to_action \
     --entrypoint meeting_agent/agent.py \
     --requirements-file requirements.txt \
     --region us-east-1 \
     --deployment-type container \
     --ecr auto \
     --non-interactive

   # 2) Deploy: push image to ECR and provision the runtime, injecting model env vars
   agentcore deploy --agent meeting_to_action \
     --env MODEL_PROVIDER=bedrock \
     --env AWS_REGION=us-east-1 \
     --env BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
   ```
   This packages the app into a container, pushes it to ECR
   (`<account>.dkr.ecr.us-east-1.amazonaws.com/bedrock-agentcore-meeting_to_action`),
   and provisions the AgentCore runtime (execution role
   `AmazonBedrockAgentCoreSDKRuntime-<region>-<id>`, Memory namespace
   `meeting_to_action_mem`; the model and region are injected via `--env`). See
   `.bedrock_agentcore.yaml` for the full generated config.
4. Grant the runtime's execution role `bedrock:InvokeModel` / `bedrock:InvokeModelWithResponseStream`
   and `memory` permissions (the role already has these; see *Status* below).
5. In production, enable real email with `EMAIL_SENDER=ses` and store SMTP/SES
   credentials in **AWS Secrets Manager** — never in code.

The agent is wrapped in `BedrockAgentCoreApp` and exposed via `app.run()` — see
`meeting_agent/agent.py` (`handler` entrypoint).

## Current status

- **Bedrock / Anthropic model invocation is pending account-level access.** The
  runtime role already has `bedrock:InvokeModel` (no denies), but the chosen model
  returns a NOT_AVAILABLE / "Error 002" — this is **account model-access approval**,
  not an IAM problem. **Do not** redeploy/invoke AgentCore until the model is
  enabled in the AWS console.
- **Live demo runs against Groq** as a real-model alternative with identical logic
  (`MODEL_PROVIDER=groq`). Note: `llama-3.3-70b-versatile` is **not** available in
  this organization (404 `model_not_found`); set `GROQ_MODEL_ID` to an available
  model. Verified-working on this account: `qwen/qwen3.8-27b`, `openai/gpt-oss-120b`.
- **Real email (non-SES)** is supported locally via `EMAIL_PROVIDER=smtp` (Gmail
  SMTP). Credentials live in `groq.env` as `smtp_email` / `smtp_password`
  (Gmail **app password**). `SimulatedEmailSender` remains the default so you can
  flip back to offline instantly.
- A convenience note: `run_demo.sh` parses `groq.env` **without sourcing it**
  (the file mixes `KEY = VALUE` lines, a bare token, and blanks — sourcing a bare
  token executes it as a shell command). If you edit `groq.env`, keep one secret
  per `KEY=value` line (spaces around `=` are tolerated).

## Contributing

PRs welcome. `meeting_agent.py` / `backend.api` are fully typed and pytest'd; keep
the offline `FakeLLM` path green. Please **never** commit `groq.env`, `github.env`,
or `credentials` — they are gitignored.

## License

MIT — see [LICENSE](LICENSE).
