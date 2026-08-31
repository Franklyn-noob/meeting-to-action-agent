# Architecture Notes

## High level

```
            ┌──────────────────────────────────────────────────────────────┐
            │                       Bedrock AgentCore Runtime               │
            │  (agentcore deploy → BedrockAgentCoreApp, app.run())          │
            │                                                               │
            │   ┌──────────────┐   ┌────────────────────────────────────┐  │
            │   │ Strands Agent│──▶│ @tool wrappers (extract/create/draft/│  │
            │   │  (agent.py)  │   │  check/markDone/current_time)        │  │
            │   └──────────────┘   └────────────────────────────────────┘  │
            │              │              │                               │
            │      model  │      ┌───────▼────────┐   AgentCore Memory     │
            │              │      │ BedrockModel   │  (task/escalation      │
            │              │      │ (deploy)      │   state)              │
            │              │      └───────┬────────┘                       │
            └──────────────────────────────┼──────────────────────────────┘
            │                              │
   ┌────────┴────────┐          ┌──────────┴────────────┐
   │  FastAPI Backend│          │  AWS services         │
   │  backend/api.py │◀─────────│  Bedrock, Memory,     │
   │  (uvicorn)      │  HTTP    │  Secrets Manager(SES) │
   └────────┬────────┘          └───────────────────────┘
            │
   ┌────────┴────────┐
   │  React Dashboard │  (frontend/, built → frontend/dist,
   │  (Vite+Tailwind) │   served statically by FastAPI)
   └─────────────────┘
```

## Strands agent + tools

`meeting_agent/agent.py` builds a `strands.Agent` with system prompt
`AGENT_SYSTEM` and the `@tool`-wrapped functions from `meeting_agent/tools/`:

- `extractActionItems` — LLM extraction → `ActionItem[]` with `owner_confidence`
  / `ambiguous_owner`.
- `createTask` — validates, persists a `Task`, classifies it by due date.
- `draftFollowupEmail` — LLM drafts a recap + per-owner assignments; sends via
  `EmailSender` (simulated locally, SES in deploy).
- `checkOverdueAndEscalate` — the "runs quietly" background check: escalates
  only on overdue / ambiguous-owner; silent `auto_handled` otherwise.
- `markTaskDone`, `current_time`.

Each tool is a **separate, testable module**: a pure `run(...)`/core function
(takes an explicit `llm` and/or `store` dependency) plus a thin `@tool`
wrapper that resolves those from env-driven singletons. This is what lets the
logic be unit-tested offline with a `FakeLLM`.

## State management (AgentCore Memory fit)

`meeting_agent/store.py` exposes a `TaskStore` ABC with two implementations:

- **`LocalJsonStore`** — default for local/demo/tests; writes JSON files under
  `data/`. Fully offline, no AWS.
- **`AgentCoreMemoryStore`** — deploy-phase; uses `bedrock_agentcore.memory.
  MemoryClient` to persist tasks and activity as structured records.

`get_store()` selects `AgentCoreMemoryStore` only when `PERSISTENCE=memory` and
AWS credentials are present; otherwise `LocalJsonStore`. This lets the same
repo run offline (JSON files) and on AgentCore (native Memory service) with no
code change.

## Model provider

`meeting_agent/llm.py` defines a small `LLM` protocol used by the extraction
and email-drafting tools. Three implementations:

- `FakeLLM` (tests / offline demo) — deterministic canned JSON, keyed by
  transcript substring (see `meeting_agent/sample_data.py`).
- `OpenAILLM` — OpenAI-compatible (e.g. Ollama) for local live runs.
- `BedrockLLM` — Amazon Bedrock Converse for the deployed runtime.

`MODEL_PROVIDER` (local | bedrock | fake) selects the provider, so the local
demo can run fully offline while the deployed runtime uses Bedrock.

## Local vs deployed runtime

- **Local / demo:** `backend/api.py` (FastAPI) runs the `orchestrator.process_
  transcript` pipeline, which composes the tool cores using `get_llm()` and
  `get_store()`. This is the offline-friendly path used by `run_demo.sh` and the
  test suite.
- **Deployed on AgentCore:** `meeting_agent/agent.py` instantiates the Strands
  `Agent` (BedrockModel) and is wrapped in `BedrockAgentCoreApp`; the
  `@app.entrypoint` handler drives the agent tool loop. Observability is
  enabled on the runtime; see the deploy section of the README.

## Observability / "runs quietly"

Every action is recorded as an `ActivityEvent` with a `kind` of
`auto_handled` or `escalation`. The dashboard activity-log panel renders these
with a distinct red highlight for escalations (⚠) — the visual signal judges
look for — and the `/` SSE feed updates live.
