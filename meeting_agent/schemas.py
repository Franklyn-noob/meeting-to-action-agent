"""Shared data schemas for the Meeting-to-Action Agent.

These Pydantic models are the single source of truth shared across the
Strands tools, the persistence store and the FastAPI backend / dashboard.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    import uuid

    return uuid.uuid4().hex


class TaskStatus(str, Enum):
    ON_TRACK = "on_track"
    DONE = "done"
    OVERDUE = "overdue"
    NEEDS_ATTENTION = "needs_attention"  # ambiguous owner awaiting user input


class EscalationReason(str, Enum):
    OVERDUE = "overdue"
    AMBIGEROUS_OWNER = "ambiguous_owner"


class ActivityKind(str, Enum):
    AUTO_HANDLED = "auto_handled"  # silent, agent handled it
    ESCALATION = "escalation"      # surfaced to the user


class ActionItem(BaseModel):
    """A single action item extracted from a transcript."""

    description: str
    owner: Optional[str] = None
    owner_evidence: Optional[str] = None
    owner_confidence: float = 0.0  # 0.0 .. 1.0
    ambiguous_owner: bool = False
    due_date: Optional[date] = None
    due_date_evidence: Optional[str] = None


class Task(BaseModel):
    """A persisted action item with tracking state."""

    id: str = Field(default_factory=_uuid)
    transcript_source: str
    description: str
    owner: Optional[str] = None
    owner_confidence: float = 0.0
    due_date: Optional[date] = None
    status: TaskStatus = TaskStatus.ON_TRACK
    created_at: datetime = Field(default_factory=_utcnow)
    completed_at: Optional[datetime] = None
    escalation_reason: Optional[EscalationReason] = None  # set only when escalated


class ActivityEvent(BaseModel):
    """A single event in the agent activity log.

    `kind` distinguishes silent auto-handled actions from user surfaced
    escalations — the most important visual signal for judges.
    """

    timestamp: datetime = Field(default_factory=_utcnow)
    kind: ActivityKind
    summary: str
    task_ids: list[str] = Field(default_factory=list)
    escalation_reason: Optional[EscalationReason] = None
