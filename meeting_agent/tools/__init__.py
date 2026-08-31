"""Strands tools for the Meeting-to-Action Agent.

Each tool module exposes:
* a snake_case core function (``run(...)`` style) — pure logic, taking explicit
  ``llm``/``store`` dependencies so it is unit-testable offline.
* a ``@tool``-wrapped CamelCase function — the version the Strands ``Agent``
  calls. These are what ``agent.py`` imports.
"""
from __future__ import annotations

from meeting_agent.tools.current_time import current_time, now
from meeting_agent.tools.extract_action_items import extractActionItems, extract_action_items, to_action_item
from meeting_agent.tools.create_task import createTask, create_task
from meeting_agent.tools.draft_followup_email import draftFollowupEmail, draft_followup_email
from meeting_agent.tools.check_overdue_and_escalate import checkOverdueAndEscalate, check_overdue_and_escalate
from meeting_agent.tools.mark_done import markTaskDone, mark_task_done

__all__ = [
    # Strands @tool wrappers (used by the agent)
    "current_time",
    "extractActionItems",
    "createTask",
    "draftFollowupEmail",
    "checkOverdueAndEscalate",
    "markTaskDone",
    # snake_case cores (used by orchestrator/tests)
    "now",
    "extract_action_items",
    "to_action_item",
    "create_task",
    "draft_followup_email",
    "check_overdue_and_escalate",
    "mark_task_done",
]
