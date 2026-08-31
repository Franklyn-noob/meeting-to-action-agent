"""Tool: draft (and, in deployed mode, send) a meeting follow-up email.

The email summarises the meeting and assigns each action item to its owner.
Locally the email is *simulated* (logged), never transmitted and never
includes credentials — credentials are wired only in the deploy phase via
Secrets Manager / SES.
"""
from __future__ import annotations

import logging
from typing import Optional

from strands import tool

from meeting_agent.email import EmailDraft, get_email_sender
from meeting_agent.llm import LLM, get_llm
from meeting_agent.schemas import ActivityEvent, ActivityKind, Task, TaskStatus
from meeting_agent.store import TaskStore, get_store
from meeting_agent.tools.current_time import now

logger = logging.getLogger(__name__)

DRAFT_SYSTEM = (
    "You are a concise, professional executive assistant. Produce a meeting "
    "follow-up email: a short recap of the meeting and a bulleted list of "
    "action items grouped by owner. Do not ask questions; just summarise and "
    "assign clearly."
)


def _summarise(tasks: list[Task]) -> str:
    if not tasks:
        return "No action items were captured in this meeting."
    return "\n".join(f"- {t.owner or 'Unassigned'}: {t.description}" for t in tasks)


def draft_followup_email(
    tasks: list[Task],
    source: str = "transcript",
    llm: Optional[LLM] = None,
    store: Optional[TaskStore] = None,
    sender=None,
    now_dt: Optional = None,
) -> EmailDraft:
    """Draft a recap email for the given tasks and (simulate) send it."""
    llm = llm or get_llm()
    store = store or get_store()
    now_dt = now_dt or now()  # noqa: F841 - available for future timestamping
    sender = sender or get_email_sender()

    owners = sorted({t.owner for t in tasks if t.owner})
    prompt = (
        f"Meeting: {source}\n\n"
        f"Action items:\n{_summarise(tasks)}\n\n"
        f"Draft a concise follow-up email: a short recap and a bulleted list of "
        f"action items grouped by owner. Recipients = the owners listed. Subject "
        f"should start with '[Meeting Follow-up]'."
    )
    schema = {
        "type": "object",
        "properties": {
            "subject": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["subject", "body"],
    }
    data = llm.structured(schema, prompt, system_prompt=DRAFT_SYSTEM) or {}
    draft = EmailDraft(
        to=[
            f"{o} <{o.lower().replace(' ', '.')}@example.com>" for o in owners
        ],
        subject=data.get("subject") or f"[Meeting Follow-up] {source}",
        body=data.get("body") or "",
    )
    receipt = sender.send(draft)
    logger.info("Email %s: %s", draft.subject, receipt.get("status"))
    store.log_activity(
        ActivityEvent(
            kind=ActivityKind.AUTO_HANDLED,
            summary=(
                f"Drafted/sent follow-up email '{draft.subject}' "
                f"to {len(draft.to)} recipient(s)"
            ),
            task_ids=[t.id for t in tasks],
        )
    )
    return draft


@tool(name="draftFollowupEmail", description="Draft and send (simulated locally) a meeting follow-up email summarising and assigning action items.")
def draftFollowupEmail(source: str = "transcript") -> dict:
    """Draft + send (simulated) follow-up email for all open tasks of a meeting."""
    from meeting_agent.schemas import Task  # noqa: F811 - local import avoids cycle

    store = get_store()
    tasks = [
        t
        for t in store.list_tasks()
        if t.transcript_source == source and t.status != TaskStatus.DONE
    ]
    draft = draft_followup_email(tasks, source=source, store=store)
    return {"to": draft.to, "subject": draft.subject, "body": draft.body}
