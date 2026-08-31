"""LLM abstraction + JSON parsing tests."""
from meeting_agent.llm import FakeLLM, _parse_json


def test_parse_json_plain():
    assert _parse_json('{"a": 1}') == {"a": 1}


def test_parse_json_fence():
    assert _parse_json("```json\n{\"a\": 1}\n```") == {"a": 1}


def test_parse_json_recover_from_prose():
    assert _parse_json("Here: {\"a\":1, \"b\":2} end") == {"a": 1, "b": 2}


def test_parse_json_invalid():
    assert _parse_json("no json here") is None


def test_fakellm_structured_substring_match():
    llm = FakeLLM(structured_fixture={"marker": '{"items":[]}'})
    assert llm.structured({}, "contains marker text") == {"items": []}


def test_fakellm_default_empty():
    assert FakeLLM().structured({}, "anything") == {}


def test_fakellm_text_fixture():
    llm = FakeLLM(text_fixture={"hello": "hi there"})
    assert llm.generate("say hello") == "hi there"
