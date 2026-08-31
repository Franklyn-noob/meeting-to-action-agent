"""extract_action_items tool core tests (offline, FakeLLM)."""
from meeting_agent.llm import FakeLLM
from meeting_agent.sample_data import AMBIGUOUS_FIXTURE, CLEAN_FIXTURE
from meeting_agent.tools.extract_action_items import extract_action_items


def test_extract_clean_has_no_ambiguity():
    llm = FakeLLM(structured_fixture={"acme sprint": CLEAN_FIXTURE})
    items = extract_action_items("Acme sprint planning. Alice docs. Bob staging.", llm=llm)
    assert len(items) == 2
    assert items[0].owner == "Alice"
    assert items[0].ambiguous_owner is False
    assert items[0].owner_confidence > 0.5
    assert items[0].due_date is not None
    assert items[1].owner == "Bob"


def test_extract_ambiguous_owner_flagged():
    llm = FakeLLM(structured_fixture={"post-mortem": AMBIGUOUS_FIXTURE})
    items = extract_action_items("Post-mortem. Investigate bug. Eve report.", llm=llm)
    assert len(items) == 2
    amb = items[0]
    assert amb.owner is None
    assert amb.ambiguous_owner is True
    assert amb.owner_confidence == 0.2  # low confidence when ambiguous
    assert items[1].owner == "Eve"


def test_extract_empty_when_no_match():
    # FakeLLM with no matching fixture returns {} -> no items.
    items = extract_action_items("random text with no fixture key", llm=FakeLLM())
    assert items == []


def test_extract_returns_action_item_models():
    llm = FakeLLM(structured_fixture={"acme sprint": CLEAN_FIXTURE})
    from meeting_agent.schemas import ActionItem

    items = extract_action_items("Acme sprint planning...", llm=llm)
    assert all(isinstance(i, ActionItem) for i in items)
