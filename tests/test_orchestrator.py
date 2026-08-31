"""End-to-end pipeline + escalation logic tests."""
from datetime import date, datetime, timezone

from meeting_agent.schemas import ActivityKind, Task, TaskStatus
from meeting_agent.sample_data import SEED_TRANSCRIPTS, expected_escalations
from meeting_agent.orchestrator import process_transcript
from meeting_agent.scheduler import run_daily_check
from meeting_agent.tools.check_overdue_and_escalate import check_overdue_and_escalate
from meeting_agent.tools.mark_done import mark_task_done


def test_full_pipeline_on_samples(demo_llm, temp_store):
    for src, txt in SEED_TRANSCRIPTS.items():
        r = process_transcript(txt, source=src, llm=demo_llm, store=temp_store)
        assert len(r.tasks) == 2
        assert len(r.escalations) == expected_escalations(src)


def test_pipeline_emits_distinct_activity_kinds(demo_llm, temp_store):
    process_transcript(list(SEED_TRANSCRIPTS.values())[1], source="p", llm=demo_llm, store=temp_store)
    feed = temp_store.activity_feed()
    kinds = {a.kind for a in feed}
    assert ActivityKind.AUTO_HANDLED in kinds
    # the overdue sample surfaces exactly one escalation
    esc = [a for a in feed if a.kind == ActivityKind.ESCALATION]
    assert len(esc) == 1
    assert esc[0].escalation_reason.value == "overdue"


def test_check_classifies_overdue_ambiguous_and_clean(temp_store):
    now = datetime(2026, 8, 31, tzinfo=timezone.utc)
    temp_store.add_task(Task(transcript_source="m", description="past due", owner="A", owner_confidence=0.9, due_date=date(2024, 1, 1)))
    temp_store.add_task(Task(transcript_source="m", description="unowned", owner=None, owner_confidence=0.2))
    temp_store.add_task(Task(transcript_source="m", description="fine", owner="B", owner_confidence=0.9, due_date=date(2030, 1, 1)))
    esc = check_overdue_and_escalate(store=temp_store, now_dt=now)
    assert len(esc) == 2
    assert {e.escalation_reason.value for e in esc} == {"overdue", "ambiguous_owner"}
    by = {t.description: t.status for t in temp_store.list_tasks()}
    assert by["past due"] == TaskStatus.OVERDUE
    assert by["unowned"] == TaskStatus.NEEDS_ATTENTION
    assert by["fine"] == TaskStatus.ON_TRACK


def test_check_skips_done_tasks(temp_store):
    t = Task(transcript_source="m", description="done", status=TaskStatus.DONE, completed_at=datetime.now(timezone.utc))
    temp_store.add_task(t)
    esc = check_overdue_and_escalate(store=temp_store, now_dt=datetime(2026, 8, 31, tzinfo=timezone.utc))
    assert esc == []
    # only the auto-handled summary event
    assert len(temp_store.activity_feed()) == 1
    assert temp_store.activity_feed()[0].kind == ActivityKind.AUTO_HANDLED


def test_check_is_idempotent(temp_store):
    now = datetime(2026, 8, 31, tzinfo=timezone.utc)
    temp_store.add_task(Task(transcript_source="m", description="past due", owner="A", owner_confidence=0.9, due_date=date(2024, 1, 1)))
    check_overdue_and_escalate(store=temp_store, now_dt=now)
    second = check_overdue_and_escalate(store=temp_store, now_dt=now)
    assert second == []  # no re-escalation of already-flagged task


def test_daily_check_does_not_refire(temp_store):
    now = datetime(2026, 8, 31, tzinfo=timezone.utc)
    temp_store.add_task(Task(transcript_source="m", description="past due", owner="A", owner_confidence=0.9, due_date=date(2024, 1, 1)))
    run_daily_check(force=True, store=temp_store, now_dt=now)
    again = run_daily_check(force=True, store=temp_store, now_dt=now)
    assert again == []


def test_mark_done(temp_store):
    t = Task(transcript_source="m", description="x", status=TaskStatus.ON_TRACK)
    temp_store.add_task(t)
    assert mark_task_done(t.id, store=temp_store) is True
    assert temp_store.get_task(t.id).status == TaskStatus.DONE
    assert mark_task_done("nope", store=temp_store) is False
