"""Tool: mark a task done."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from strands import tool

from meeting_agent.schemas import ActivityEvent, ActivityKind, TaskStatus
from meeting_agent.store import TaskStore, get_store
from meeting_agent.tools.current_time import now


def mark_task_done(
    task_id: str,
    store: Optional[TaskStore] = None,
    now_dt: Optional[datetime] = None,
) -> bool:
    """Mark a task complete. Returns True if a task was found and updated."""
    store = store or get_store()
    now_dt = now_dt or now()
    task = store.get_task(task_id)
    if task is None:
        return False
    task.status = TaskStatus.DONE
    task.completed_at = now_dt
    task.escalation_reason = None
    store.update_task(task)
    store.log_activity(
        ActivityEvent(
            kind=ActivityKind.AUTO_HANDLED,
            summary=f"Completed task: {task.description[:80]}",
            task_ids=[task.id],
        )
    )
    return True


@tool(name="markTaskDone", description="Mark a task complete and log the activity.")
def markTaskDone(task_id: str) -> dict:
    """Mark a task done; idempotent. Returns {'done': bool, 'task_id': str}."""
    ok = mark_task_done(task_id, store=get_store())
    return {"done": ok, "task_id": task_id}
