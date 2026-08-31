"""FastAPI backend tests (offline, MODEL_PROVIDER=fake)."""
from fastapi.testclient import TestClient

from backend.api import app


def test_demo_state_seeded(fake_env):
    with TestClient(app) as c:
        s = c.get("/api/state").json()
        assert s["counts"]["total_tasks"] == 6
        assert s["counts"]["escalations"] == 2
        esc = c.get("/api/escalations").json()
        assert {e["escalation_reason"] for e in esc} == {"overdue", "ambiguous_owner"}
        by = s["tasks_by_status"]
        assert len(by["on_track"]) == 4
        assert len(by["overdue"]) == 1
        assert len(by["needs_attention"]) == 1
        assert len(by["done"]) == 0


def test_config_endpoint(fake_env):
    with TestClient(app) as c:
        assert c.get("/api/config").json()["model_provider"] == "fake"


def test_process_transcript_clean(fake_env):
    with TestClient(app) as c:
        r = c.post(
            "/api/process-transcript",
            json={"transcript": "Acme sprint planning for Q3. Alice docs. Bob staging.", "source": "live"},
        ).json()
        assert len(r["tasks"]) == 2
        assert len(r["escalations"]) == 0
        assert r["email"]["subject"].startswith("[Meeting Follow-up]")


def test_mark_done_and_daily_check_idempotent(fake_env):
    with TestClient(app) as c:
        tasks = c.get("/api/tasks").json()
        tid = tasks[0]["id"]
        assert c.post(f"/api/tasks/{tid}/done").json()["done"] is True
        dc = c.post("/api/run-daily-check").json()
        assert dc["count"] == 0  # existing escalations not re-surfaced
        sse = c.get("/api/activity/sse?once=true")
        assert sse.status_code == 200


def test_escalations_only(fake_env):
    with TestClient(app) as c:
        all_act = c.get("/api/activity").json()
        esc = c.get("/api/escalations").json()
        assert all(a["kind"] != "escalation" for a in all_act) is False  # some escalations exist
        assert len(esc) == 2
