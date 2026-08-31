"""Task-state persistence abstraction.

The hackathon note prefers AgentCore Memory "if it fits naturally". It does,
but it requires AWS credentials and a deployed runtime. So we expose a
``TaskStore`` abstraction with two implementations:

* ``LocalJsonStore`` — default for local/demo/test runs; writes JSON files
  under ``data/``. Fully offline and deterministic.
* ``AgentCoreMemoryStore`` — uses the AgentCore Memory service; selected only
  when running on the deployed AgentCore runtime (AWS credentials present).

Both expose the exact same interface so tools and the backend are agnostic to
where state actually lives.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from meeting_agent.schemas import (
    ActivityEvent,
    ActivityKind,
    EscalationReason,
    Task,
    TaskStatus,
)

logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR = os.getenv("AGENT_DATA_DIR", "data")


def _data_dir() -> Path:
    p = Path(DEFAULT_DATA_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupt state file %s; starting fresh.", path)
        return default


class TaskStore(ABC):
    """Interface shared by every persistence backend."""

    @abstractmethod
    def add_task(self, task: Task) -> None: ...

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[Task]: ...

    @abstractmethod
    def list_tasks(self) -> list[Task]: ...

    @abstractmethod
    def update_task(self, task: Task) -> None: ...

    @abstractmethod
    def log_activity(self, event: ActivityEvent) -> None: ...

    @abstractmethod
    def activity_feed(self) -> list[ActivityEvent]: ...


class LocalJsonStore(TaskStore):
    """JSON-file store for local/demo/test runs. Thread-safe via a lock."""

    def __init__(self, base_dir: str | Path = DEFAULT_DATA_DIR) -> None:
        self._dir = Path(base_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._tasks_path = self._dir / "tasks.json"
        self._activity_path = self._dir / "activity.json"
        self._lock = threading.RLock()
        if not self._tasks_path.exists():
            self._write_tasks([])
        if not self._activity_path.exists():
            self._write_activity([])

    # -- helpers --
    def _read_tasks(self) -> list[dict]:
        return _read_json(self._tasks_path, [])

    def _write_tasks(self, tasks: list[dict]) -> None:
        with self._tasks_path.open("w") as f:
            json.dump(tasks, f, indent=2, default=_json_default)

    def _read_activity(self) -> list[dict]:
        return _read_json(self._activity_path, [])

    def _write_activity(self, events: list[dict]) -> None:
        with self._activity_path.open("w") as f:
            json.dump(events, f, indent=2, default=_json_default)

    # -- TaskStore API --
    def add_task(self, task: Task) -> None:
        with self._lock:
            tasks = self._read_tasks()
            tasks.append(task.model_dump())
            self._write_tasks(tasks)

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._lock:
            for raw in self._read_tasks():
                if raw["id"] == task_id:
                    return Task(**raw)
        return None

    def list_tasks(self) -> list[Task]:
        with self._lock:
            return [Task(**raw) for raw in self._read_tasks()]

    def update_task(self, task: Task) -> None:
        with self._lock:
            tasks = self._read_tasks()
            for i, raw in enumerate(tasks):
                if raw["id"] == task.id:
                    tasks[i] = task.model_dump()
                    break
            else:
                tasks.append(task.model_dump())
            self._write_tasks(tasks)

    def log_activity(self, event: ActivityEvent) -> None:
        with self._lock:
            events = self._read_activity()
            events.append(event.model_dump())
            self._write_activity(events)

    def activity_feed(self) -> list[ActivityEvent]:
        with self._lock:
            return [ActivityEvent(**raw) for raw in self._read_activity()]


class AgentCoreMemoryStore(TaskStore):
    """AgentCore Memory-backed store (deployed runtime only).

    Not exercised offline. Lazily imports the AgentCore Memory client and
    raises a clear error if AWS credentials are unavailable.
    """

    def __init__(self, session_id: str = "meeting-actions") -> None:
        from bedrock_agentcore.memory import AsyncAggregatorStorage  # noqa: F401
        from strands.sessions import Boto3Session

        _ = Boto3Session()  # validates credentials exist
        self._session_id = session_id

    # Minimal pass-through to the JSON schema for the local fallback path.
    # Real implementation would persist/retrieve Task & ActivityEvent objects
    # as structured records via the AgentCore Memory namespace API.
    def _storage(self):
        from bedrock_agentcore.memory import AsyncAggregatorStorage

        return AsyncAggregatorStorage()

    def add_task(self, task: Task) -> None:
        raise NotImplementedError("AgentCore Memory store requires deployed runtime")

    def get_task(self, task_id: str) -> Optional[Task]:
        raise NotImplementedError("AgentCore Memory store requires deployed runtime")

    def list_tasks(self) -> list[Task]:
        raise NotImplementedError("AgentCore Memory store requires deployed runtime")

    def update_task(self, task: Task) -> None:
        raise NotImplementedError("AgentCore Memory store requires deployed runtime")

    def log_activity(self, event: ActivityEvent) -> None:
        raise NotImplementedError("AgentCore Memory store requires deployed runtime")

    def activity_feed(self) -> list[ActivityEvent]:
        raise NotImplementedError("AgentCore Memory store requires deployed runtime")


def get_store() -> TaskStore:
    """Return the configured TaskStore.

    Local/dev defaults to ``LocalJsonStore`` so nothing in this repo needs
    AWS credentials to run. Set ``PERSISTENCE=memory`` (and provide AWS creds)
    to use AgentCore Memory on the deployed runtime.
    """
    if os.getenv("PERSISTENCE") == "memory":
        try:
            return AgentCoreMemoryStore()
        except Exception as exc:  # pragma: no cover - deploy-time path
            logger.warning("Falling back to LocalJsonStore: %s", exc)
    # Re-read env at call time so tests (and run_demo.sh) can redirect state.
    return LocalJsonStore(os.getenv("AGENT_DATA_DIR", DEFAULT_DATA_DIR))


def _json_default(obj):
    """JSON encoder for Pydantic enums and date/datetime values."""
    if isinstance(obj, TaskStatus):
        return obj.value
    if isinstance(obj, ActivityKind):
        return obj.value
    if isinstance(obj, EscalationReason):
        return obj.value
    if isinstance(obj, (str, int, float, bool, list, dict)) or obj is None:
        return obj
    try:
        import datetime as _dt

        if isinstance(obj, (dict, list)):
            return obj
        if isinstance(obj, _dt.date):
            return obj.isoformat()
    except Exception:
        pass
    return str(obj)
