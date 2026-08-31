"""Strands Agent + BedrockAgentCoreApp wiring.

This module is the **deployment** artifact: a real Strands ``Agent`` composed of
the four task tools plus a local ``current_time`` tool, wrapped in a
``BedrockAgentCoreApp`` runtime entrypoint (``app.run()``).

For **local demo + backend + tests** we use the :mod:`meeting_agent.orchestrator`
pipeline directly (offline-friendly, env-driven model) — see ``backend/api.py``.
The Strands agent here is what gets deployed to AgentCore; it shares the same
tool modules and the same env-driven provider selection as the orchestrator, so
behaviour is identical whether invoked locally (Ollama) or on Bedrock.
"""
from __future__ import annotations

import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent

from meeting_agent.tools import (
    checkOverdueAndEscalate,
    createTask,
    current_time,
    draftFollowupEmail,
    extractActionItems,
    markTaskDone,
)

AGENT_SYSTEM = """You are "Actioneer", an autonomous meeting-to-action agent.
Your job is to turn meeting transcripts into tracked action items and keep
owners on track — but you only surface a problem to the human when a task is
overdue or ownership is ambiguous. Operate silently otherwise.

Workflow per transcript:
1. Call extractActionItems on the transcript to get structured items.
2. Call createTask once per item to persist it.
3. Call draftFollowupEmail to summarise and assign (send is simulated locally).
4. Call checkOverdueAndEscalate to review and surface only real escalations.
Group your tool calls and avoid repeating work. Be concise in your final reply:
a one-line status and any escalation that needs the human."""


def get_strands_model():
    """Build the Strands model used by the agent (env-driven)."""
    provider = os.getenv("MODEL_PROVIDER", "local").lower()
    if provider == "bedrock":
        from strands.models.bedrock import BedrockModel

        return BedrockModel(
            model_id=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
            region_name=os.getenv("AWS_REGION"),
        )
    # local / default: OpenAI-compatible (e.g. Ollama)
    from openai import Client
    from strands.models.openai import OpenAIModel

    return OpenAIModel(
        client=Client(
            base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.getenv("OPENAI_API_KEY", "ollama"),
        ),
        model_id=os.getenv("MODEL_ID", "llama3.3"),
    )


def build_agent() -> Agent:
    """Construct the Strands Agent with its tools and system prompt."""
    return Agent(
        model=get_strands_model(),
        tools=[
            extractActionItems,
            createTask,
            draftFollowupEmail,
            checkOverdueAndEscalate,
            markTaskDone,
            current_time,
        ],
        system_prompt=AGENT_SYSTEM,
    )


# --- Bedrock AgentCore runtime wrapper -------------------------------------
app = BedrockAgentCoreApp()


@app.entrypoint
def handler(event, context):
    """AgentCore Runtime entrypoint: process a meeting transcript.

    Expected event: ``{"transcript": "...", "source": "optional meeting name"}``.
    The Strands agent orchestrates the tools end-to-end.
    """
    agent = build_agent()
    transcript = event.get("transcript") or event.get("prompt") or ""
    source = event.get("source", "transcript")
    # The agent's system prompt drives the full extract->create->email->check flow.
    reply = agent(
        f"Meeting \"{source}\" transcript:\n{transcript}\nPlease run the full workflow."
    )
    return {"response": str(reply)}


if __name__ == "__main__" and os.getenv("AGENTCORE_DEPLOY") == "1":
    # `agentcore deploy` runs this; locally it's started by agentcore/socat.
    app.run()
