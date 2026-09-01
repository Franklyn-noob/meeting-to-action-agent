"""current_time tool — backed by the official ``strands_tools`` implementation.

Strands ships its built-in tools (including ``current_time``) via the
``strands-agents-tools`` package on PyPI, imported as
``from strands_tools.current_time import current_time``. We use that exact
official tool for the Strands ``Agent`` and expose a sync ``now()`` that the
pipeline calls for all due-date logic, so wall-clock logic routes through the
real implementation instead of a local stand-in.

Note: ``strands_tools.current_time`` is deprecated upstream (in favour of the
ContextInjector plugin) but remains fully functional; its deprecation noise is
silenced here so local/demo runs stay readable.
"""
from __future__ import annotations

import logging
import warnings
from datetime import datetime

from strands_tools.current_time import current_time

# Silence the upstream deprecation chatter on every call:
#   * `logger.warning("DEPRECATION WARNING: ...")` emitted by the tool body
#   * the PEP 702 `@deprecated` DeprecationWarning emitted on each invocation
logging.getLogger("strands_tools.current_time").setLevel(logging.ERROR)

__all__ = ["current_time", "now"]


def now() -> datetime:
    """Current UTC datetime, sourced from the official strands_tools current_time."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        iso = current_time()
    return datetime.fromisoformat(iso)
