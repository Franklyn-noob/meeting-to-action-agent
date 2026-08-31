"""Tool: background daily check — escalate ONLY on real reasons.

This is the heart of the "runs quietly" design. The daily check reviews every
open task and surfaces a user-facing escalation **only** when:

  (a) the task is overdue (due date passed), or
  (b) ownership is ambiguous (no clear owner / low confidence).

Every other task is silently marked ``on_track``. Escalations and silent
auto-handled actions are logged with distinct ``ActivityKind`` values so the
dashboard can show "auto-handled" vs "needs your input".
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from strands import tool

from meeting_agent.schemas import (
    ActivityEvent,
    ActivityKind,
    EscalationReason,
    Task,
    TaskStatus,
)
from meeting_agent.store import TaskStore, get_store
from meeting_agent.tools.current_time import now

logger = logging.getLogger(__name__)

# Tasks with confidence below this threshold count as ambiguous ownership.
AMBIGUOUS_OWNER_CONFIDENCE = 0.5


def _classify(task: Task, now_dt: datetime) -> Optional[EscalationReason]:
    """Return an escalation reason if the task needs user attention, else None."""
    if task.due_date and task.due_date < now_dt.date():
        return EscalationReason.OVERDUE
    if task.owner is None or task.owner_confidence < AMBIGUOUS_OWNER_CONFIDENCE:
        return EscalationReason.AMBIGEROUS_OWNER
    return None


def check_overdue_and_escalate(
    store: Optional[TaskStore] = None, now_dt: Optional[datetime] = None
) -> list[ActivityEvent]:
    """Review open tasks; return the list of escalation activity events.

    Mutates task statuses in the store and writes distinct activity events for
    escalations (``ESCALATION``) vs silent checks (``AUTO_HANDLED``).
    """
    store = store or get_store()
    now_dt = now_dt or now()
    escalations: list[ActivityEvent] = []
    open_count = 0

    for task in store.list_tasks():
        if task.status == TaskStatus.DONE:
            continue
        open_count += 1
        reason = _classify(task, now_dt)
        if reason is not None:
            new_status = (
                TaskStatus.OVERDUE
                if reason == EscalationReason.OVERDUE
                else TaskStatus.NEEDS_ATTENTION
            )
            # Only escalate (and log) on a state *transition*, so a task that is
            # already escalated is not re-logged on every daily check.
            if task.status == new_status and task.escalation_reason == reason:
                continue
            task.status = new_status
            task.escalation_reason = reason
            store.update_task(task)
            event = ActivityEvent(
                kind=ActivityKind.ESCALATION,
                summary=(
                    f"{'Overdue' if reason == EscalationReason.OVERDUE else 'Ambiguous owner'} "
                    f"for: {task.description[:80]}"
                ),
                task_ids=[task.id],
                escalation_reason=reason,
            )
            store.log_activity(event)
            escalations.append(event)
            logger.warning("ESCALATION (%s): task %s", reason.value, task.id)

    # One silent auto-handled summary per run so the activity log shows the check
    # happened even when nothing was newly escalated.
    store.log_activity(
        ActivityEvent(
            kind=ActivityKind.AUTO_HANDLED,
            summary=(
                f"Daily check reviewed {open_count} open task(s); "
                f"{len(escalations)} newly escalated, rest on track."
            ),
            task_ids=[e.task_ids[0] for e in escalations],
        )
    )
    return escalations


@tool(name="checkOverdueAndEscalate", description="Background check: escalate only overdue or ambiguously-owned tasks. Silent otherwise.")
def checkOverdueAndEscalate() -> list[dict]:
    """Run the daily escalation check against the configured store."""
    escalations = check_overdue_and_escalate(store=get_store())
    return [
        {
            "kind": e.kind.value,
            "summary": e.summary,
            "task_ids": e.task_ids,
            "escalation_reason": e.escalation_reason.value if e.escalation_reason else None,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in escalations
    ]
