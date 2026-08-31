"""End-to-end meeting processing pipeline.

This is the runnable pipeline that powers the local demo and the FastAPI
backend. It composes the tool cores (``extract_action_items`` ->
``create_task`` -> ``check_overdue_and_escalate`` -> ``draft_followup_email``)
using the env-configured LLM and store, so it runs fully offline with a
``FakeLLM`` / ``LocalJsonStore`` and only needs credentials when deployed.
"""
from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

from meeting_agent.llm import LLM, get_llm
from meeting_agent.email import EmailDraft, get_email_sender
from meeting_agent.schemas import Task, ActivityEvent
from meeting_agent.store import TaskStore, get_store
from meeting_agent.tools.check_overdue_and_escalate import check_overdue_and_escalate
from meeting_agent.tools.create_task import create_task
from meeting_agent.tools.draft_followup_email import draft_followup_email
from meeting_agent.tools.extract_action_items import extract_action_items

logger = logging.getLogger(__name__)


class ProcessResult(BaseModel):
    """Result of processing one transcript."""

    tasks: list[Task] = Field(default_factory=list)
    escalations: list[ActivityEvent] = Field(default_factory=list)
    email: Optional[EmailDraft] = None
    activity: list[ActivityEvent] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}


def process_transcript(
    transcript: str,
    source: str = "transcript",
    llm: Optional[LLM] = None,
    store: Optional[TaskStore] = None,
) -> ProcessResult:
    """Run the full pipeline on one transcript.

    Steps:
      1. Extract structured action items (LLM).
      2. Create + persist one task per item.
      3. Run the escalation check (immediately surfaces overdue/ambiguous).
      4. Draft (simulated-send) the follow-up email.
    """
    llm = llm or get_llm()
    store = store or get_store()

    items = extract_action_items(transcript, llm=llm, source=source)
    logger.info("extract_action_items -> %d items", len(items))

    tasks: list[Task] = []
    for item in items:
        task = create_task(item, source=source, store=store)
        tasks.append(task)
    logger.info("create_task -> %d tasks persisted", len(tasks))

    escalations = check_overdue_and_escalate(store=store)
    logger.info("check_overdue_and_escalate -> %d escalation(s)", len(escalations))

    email_draft: Optional[EmailDraft] = None
    if tasks:
        email_draft = draft_followup_email(
            tasks, source=source, llm=llm, store=store, sender=get_email_sender()
        )
    logger.info("draft_followup_email -> %s", email_draft.subject if email_draft else "n/a")

    return ProcessResult(
        tasks=tasks,
        escalations=escalations,
        email=email_draft,
        activity=store.activity_feed(),
    )


def list_state(store: Optional[TaskStore] = None) -> dict:
    """Snapshot of current tasks + activity feed (for the dashboard)."""
    store = store or get_store()
    tasks = [t for t in store.list_tasks()]
    return {
        "tasks": [t.model_dump(mode="json") for t in tasks],
        "activity": [a.model_dump(mode="json") for a in store.activity_feed()],
    }
