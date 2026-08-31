"""Daily background check scheduler.

For the demo, the "daily" tick is triggered on demand (an API button / CLI
call) rather than waiting 24h. ``run_daily_check`` is idempotent within a
single wall-clock day unless ``force=True`` is passed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from meeting_agent.schemas import ActivityEvent
from meeting_agent.store import TaskStore, get_store
from meeting_agent.tools.check_overdue_and_escalate import check_overdue_and_escalate
from meeting_agent.tools.current_time import now

logger = logging.getLogger(__name__)

_last_run: dict[str, datetime] = {}
TODAY = "today"


def _today_key(now_dt: datetime) -> str:
    return now_dt.strftime("%Y-%m-%d")


def run_daily_check(
    force: bool = False,
    store: Optional[TaskStore] = None,
    now_dt: Optional[datetime] = None,
) -> list[ActivityEvent]:
    """Run the background escalation check.

    Skips if already run today unless ``force=True`` (manual/demo trigger).
    """
    store = store or get_store()
    now_dt = now_dt or now()
    key = _today_key(now_dt)
    if not force and _last_run.get(TODAY) == key:
        logger.info("Daily check already run today; skipping (use force=True).")
        return []
    _last_run[TODAY] = now_dt
    escalations = check_overdue_and_escalate(store=store, now_dt=now_dt)
    logger.info("Daily check complete: %d escalation(s)", len(escalations))
    return escalations
