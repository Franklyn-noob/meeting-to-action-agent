"""Tool: create a task record from an action item and log activity.

A newly created task is classified by its due date: a task already past due on
creation is flagged ``OVERDUE`` (the escalation tool will surface it); otherwise
``ON_TRACK``. Creating a task never escalates on its own — escalations are the
daily-check tool's job, so the agent stays silent unless the background check
says so.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from strands import tool

from meeting_agent.llm import LLM  # noqa: F401  (re-exported for type parity)
from meeting_agent.schemas import (
    ActionItem,
    ActivityEvent,
    ActivityKind,
    Task,
    TaskStatus,
)
from meeting_agent.store import TaskStore, get_store
from meeting_agent.tools.current_time import now


def classify_status(due_date: Optional, now_dt: datetime) -> TaskStatus:
    if due_date and due_date < now_dt.date():
        return TaskStatus.OVERDUE
    return TaskStatus.ON_TRACK


def create_task(
    action_item: ActionItem,
    source: str,
    store: Optional[TaskStore] = None,
    now_dt: Optional[datetime] = None,
) -> Task:
    """Persist a task from an action item and log an auto-handled activity."""
    store = store or get_store()
    now_dt = now_dt or now()
    task = Task(
        transcript_source=source,
        description=action_item.description,
        owner=action_item.owner,
        owner_confidence=action_item.owner_confidence,
        due_date=action_item.due_date,
    )
    task.status = classify_status(task.due_date, now_dt)
    store.add_task(task)
    store.log_activity(
        ActivityEvent(
            kind=ActivityKind.AUTO_HANDLED,
            summary=(
                f"Created task{' (overdue on creation)' if task.status == TaskStatus.OVERDUE else ''}"
                f" for {task.owner or 'unassigned'}: {task.description[:80]}"
            ),
            task_ids=[task.id],
        )
    )
    return task


@tool(name="createTask", description="Create and persist a task record from an action item (description, owner, due date) and return it.")
def createTask(
    description: str,
    owner: Optional[str] = None,
    owner_confidence: float = 0.0,
    ambiguous_owner: bool = False,
    due_date: Optional[str] = None,
    due_date_evidence: Optional[str] = None,
    source: str = "transcript",
) -> dict:
    """Persist a task and return its JSON form."""
    ai = ActionItem(
        description=description,
        owner=owner,
        owner_confidence=owner_confidence,
        ambiguous_owner=ambiguous_owner,
        due_date=(date.fromisoformat(due_date) if due_date else None),
        due_date_evidence=due_date_evidence,
    )
    task = create_task(ai, source=source, store=get_store())
    return task.model_dump(mode="json")
