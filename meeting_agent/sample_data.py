"""Demo data: sample transcripts + canned LLM fixtures.

In ``MODEL_PROVIDER=fake`` (offline) mode the agent runs against these
deterministic fixtures so the dashboard is fully functional with no LLM
backend installed. Each transcript contains a unique phrase that the demo
``FakeLLM`` keys its canned response on.
"""
from __future__ import annotations

from meeting_agent.llm import FakeLLM

# phrase -> canned structured-output JSON for extractActionItems
CLEAN_FIXTURE = (
    '{"items":['
    '{"description":"Write the onboarding documentation","owner":"Alice",'
    '"owner_evidence":"Alice to write the onboarding docs","owner_confidence":0.9,'
    '"ambiguous_owner":false,"due_date":"2030-12-01","due_date_evidence":"by end of sprint"},'
    '{"description":"Stand up the staging environment","owner":"Bob",'
    '"owner_evidence":"Bob will handle staging setup","owner_confidence":0.9,'
    '"ambiguous_owner":false,"due_date":null,"due_date_evidence":null}'
    ']}'
)

OVERDUE_FIXTURE = (
    '{"items":['
    '{"description":"Finalize the API contract for payments","owner":"Carol",'
    '"owner_evidence":"Carol to finalize the API contract","owner_confidence":0.9,'
    '"ambiguous_owner":false,"due_date":"2024-01-15","due_date_evidence":"due Jan 15"},'
    '{"description":"Review the security checklist","owner":"Dave",'
    '"owner_evidence":"Dave will review the checklist","owner_confidence":0.9,'
    '"ambiguous_owner":false,"due_date":"2030-06-01","due_date_evidence":"June"}'
    ']}'
)

AMBIGUOUS_FIXTURE = (
    '{"items":['
    '{"description":"Investigate the login bug","owner":null,"owner_evidence":null,'
    '"owner_confidence":0.2,"ambiguous_owner":true,"due_date":null,"due_date_evidence":null},'
    '{"description":"Write the incident report","owner":"Eve",'
    '"owner_evidence":"Eve, can you write the incident report","owner_confidence":0.9,'
    '"ambiguous_owner":false,"due_date":"2030-05-01","due_date_evidence":"by Friday"}'
    ']}'
)

# Keyed by a unique phrase present in each transcript.
DEMO_STRUCTURED_FIXTURES: dict[str, str] = {
    "acme sprint planning for q3": CLEAN_FIXTURE,
    "weekly status sync for project phoenix": OVERDUE_FIXTURE,
    "post-mortem for the login outage incident": AMBIGUOUS_FIXTURE,
}

# The three sample transcripts (mirrors sample_transcripts/*.txt used on disk).
SEED_TRANSCRIPTS: dict[str, str] = {
    "Acme Q3 Sprint Planning": """\
Acme sprint planning for Q3 — the team synced on the roadmap. Alice will write the onboarding documentation by end of sprint. Bob will handle staging setup. No open questions; everyone clear.
""",
    "Project Phoenix Weekly Status": """\
Weekly status sync for Project Phoenix. Carol, please finalize the API contract for payments — it was due Jan 15. Dave, you're on review of the security checklist by June. Action items captured.
""",
    "Login Outage Post-Mortem": """\
Post-mortem for the login outage incident. We need to investigate the root cause of the login bug — ownership TBD. Eve, can you write the incident report by Friday? Assigning the investigation pending further input.
""",
}


def build_demo_llm() -> FakeLLM:
    """FakeLLM with canned responses for the three demo transcripts."""
    return FakeLLM(structured_fixture=DEMO_STRUCTURED_FIXTURES)


def expected_escalations(source: str) -> int:
    return {"Acme Q3 Sprint Planning": 0, "Project Phoenix Weekly Status": 1,
            "Login Outage Post-Mortem": 1}.get(source, 0)
