"""Shared pytest fixtures."""
import os

import pytest


@pytest.fixture
def temp_store(tmp_path, monkeypatch):
    """A LocalJsonStore backed by an isolated temp directory."""
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    from meeting_agent.store import LocalJsonStore

    store = LocalJsonStore(str(tmp_path))
    return store


@pytest.fixture
def demo_llm():
    from meeting_agent.sample_data import build_demo_llm

    return build_demo_llm()


@pytest.fixture
def fake_env(monkeypatch, tmp_path):
    """Configure the app for fully-offline fake/demo mode on a temp store."""
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MODEL_PROVIDER", "fake")
    monkeypatch.setenv("EMAIL_SENDER", "simulated")
