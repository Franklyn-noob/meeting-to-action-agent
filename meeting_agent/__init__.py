"""Meeting-to-Action Agent.

A Strands agent that turns meeting transcripts into tracked action items,
drafts follow-up email, and only escalates to the user when a task is
overdue or ambiguous about ownership.
"""

from meeting_agent.schemas import (
    ActionItem,
    Task,
    TaskStatus,
    ActivityEvent,
    ActivityKind,
    EscalationReason,
)

__all__ = [
    "ActionItem",
    "Task",
    "TaskStatus",
    "ActivityEvent",
    "ActivityKind",
    "EscalationReason",
]

__version__ = "0.1.0"
