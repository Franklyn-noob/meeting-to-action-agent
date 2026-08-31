"""Local stand-in for ``strands_tools.current_time``.

The ``strands-tools`` package that shipped ``current_time``/``http``/``shell``
is not available in ``strands-agents==1.54``. We provide an equivalent
``current_time`` tool (same intent: a timezone-aware clock for due-date logic)
so the agent still has an injectable time tool, and note the substitution in
the README.
"""
from __future__ import annotations

from datetime import datetime, timezone

from strands import tool


def now() -> datetime:
    """Current UTC time (injectable in tests)."""
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    return now().isoformat()


@tool(name="current_time", description="Return the current UTC date and time as ISO 8601. Use for all due-date logic.")
def current_time() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return now().isoformat()
