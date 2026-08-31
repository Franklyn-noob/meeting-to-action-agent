"""Schema serialization tests."""
from datetime import date, datetime

from meeting_agent.schemas import (
    ActionItem,
    ActivityEvent,
    ActivityKind,
    EscalationReason,
    Task,
    TaskStatus,
)


def test_action_item_defaults():
    ai = ActionItem(description="Ship it")
    assert ai.owner is None
    assert ai.ambiguous_owner is False
    assert ai.owner_confidence == 0.0
    assert ai.due_date is None


def test_task_model_dump_json_is_serializable():
    t = Task(
        transcript_source="m1",
        description="Do thing",
        owner="Alice",
        due_date=date(2030, 12, 1),
        status=TaskStatus.ON_TRACK,
    )
    dumped = t.model_dump(mode="json")
    # date -> ISO string, enum -> str value
    assert dumped["due_date"] == "2030-12-01"
    assert dumped["status"] == "on_track"
    assert dumped["escalation_reason"] is None
    # round-trip
    t2 = Task(**dumped)
    assert t2.owner == "Alice"
    assert t2.due_date == date(2030, 12, 1)


def test_activity_event_serialization():
    ev = ActivityEvent(
        kind=ActivityKind.ESCALATION,
        summary="Overdue task",
        escalation_reason=EscalationReason.OVERDUE,
    )
    d = ev.model_dump(mode="json")
    assert d["kind"] == "escalation"
    assert d["escalation_reason"] == "overdue"
    assert isinstance(d["timestamp"], str)
