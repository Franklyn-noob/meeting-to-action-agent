"""LocalJsonStore tests."""
from datetime import date, datetime, timezone

from meeting_agent.schemas import (
    ActivityEvent,
    ActivityKind,
    EscalationReason,
    Task,
    TaskStatus,
)
from meeting_agent.store import LocalJsonStore


def test_add_get_list_update(temp_store):
    t = Task(transcript_source="m", description="A", owner="Alice")
    temp_store.add_task(t)
    got = temp_store.get_task(t.id)
    assert got is not None and got.description == "A"
    assert len(temp_store.list_tasks()) == 1

    t.status = TaskStatus.DONE
    t.completed_at = datetime.now(timezone.utc)
    temp_store.update_task(t)
    assert temp_store.get_task(t.id).status == TaskStatus.DONE


def test_update_unknown_task_appends(temp_store):
    t = Task(transcript_source="m", description="A")
    temp_store.update_task(t)  # not previously added -> appended
    assert len(temp_store.list_tasks()) == 1


def test_activity_log_and_feed(temp_store):
    ev = ActivityEvent(kind=ActivityKind.ESCALATION, summary="x", task_ids=["1"])
    temp_store.log_activity(ev)
    feed = temp_store.activity_feed()
    assert len(feed) == 1
    assert feed[0].kind == ActivityKind.ESCALATION


def test_persistence_roundtrip(tmp_path):
    """State survives a fresh LocalJsonStore instance on the same dir."""
    store1 = LocalJsonStore(str(tmp_path))
    store1.add_task(Task(transcript_source="m", description="A", due_date=date(2030, 1, 1)))
    ev = ActivityEvent(kind=ActivityKind.AUTO_HANDLED, summary="created", task_ids=[])
    store1.log_activity(ev)

    store2 = LocalJsonStore(str(tmp_path))
    tasks = store2.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].due_date == date(2030, 1, 1)  # date survived serialization
    assert len(store2.activity_feed()) == 1


def test_activity_json_has_enum_values(temp_store):
    temp_store.log_activity(
        ActivityEvent(
            kind=ActivityKind.ESCALATION,
            summary="amb",
            escalation_reason=EscalationReason.AMBIGEROUS_OWNER,
        )
    )
    import json, pathlib

    raw = json.loads(pathlib.Path(str(temp_store._activity_path)).read_text())
    assert raw[0]["kind"] == "escalation"
    assert raw[0]["escalation_reason"] == "ambiguous_owner"
