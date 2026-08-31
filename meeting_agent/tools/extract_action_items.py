"""Tool: extract structured action items from a meeting transcript.

Returns a list of :class:`ActionItem` with an explicit ``owner_confidence``
and ``ambiguous_owner`` flag. The ``ambiguous_owner`` flag is what later drives
the "only escalate when ambiguous" rule.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from strands import tool

from meeting_agent.llm import LLM, get_llm
from meeting_agent.schemas import ActionItem

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM = (
    "You are a meticulous meeting-assistant. From the transcript, extract every "
    "concrete action item as a JSON object with exactly these fields:\n"
    " - description (string)\n"
    " - owner (the person's full name mentioned in the transcript, or null)\n"
    " - owner_evidence (the exact phrase that pins ownership, or null)\n"
    " - owner_confidence (0.0-1.0; 1.0 if a named owner is clearly stated, "
    "0.2 if ownership is unclear/implicit)\n"
    " - ambiguous_owner (true when no clear owner can be determined)\n"
    " - due_date (ISO date YYYY-MM-DD, or null)\n"
    " - due_date_evidence (the phrase that implies the due date, or null)\n"
    "Only output the JSON. If there are no action items, return {\"items\":[]}."
)

# JSON Schema (used both as a prompt cue and validated against the parsed dict).
EXTRACTION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "owner": {"type": "string"},
                    "owner_evidence": {"type": "string"},
                    "owner_confidence": {"type": "number"},
                    "ambiguous_owner": {"type": "boolean"},
                    "due_date": {"type": "string"},
                    "due_date_evidence": {"type": "string"},
                },
                "required": ["description"],
            },
        }
    },
    "required": ["items"],
}


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except (ValueError, TypeError):
        return None


def to_action_item(d: dict) -> ActionItem:
    """Map a parsed dict to an :class:`ActionItem`, computing confidence."""
    owner = d.get("owner")
    owner_evidence = d.get("owner_evidence")
    ambiguous = bool(d.get("ambiguous_owner")) or owner is None
    if ambiguous:
        confidence = 0.2
    else:
        confidence = float(d.get("owner_confidence") or 0.8)
        confidence = max(0.0, min(1.0, confidence))
    return ActionItem(
        description=d.get("description", ""),
        owner=owner,
        owner_evidence=owner_evidence,
        owner_confidence=confidence,
        ambiguous_owner=ambiguous,
        due_date=_parse_date(d.get("due_date")),
        due_date_evidence=d.get("due_date_evidence"),
    )


def extract_action_items(
    transcript: str, llm: Optional[LLM] = None, source: str = "transcript"
) -> list[ActionItem]:
    """Extract structured action items from a transcript.

    Args:
        transcript: raw meeting transcript text.
        llm: LLM used for extraction. If None, the env-configured singleton is
            used (``get_llm``).
        source: label identifying the meeting/transcript (for traceability).

    Returns:
        List of :class:`ActionItem` with confidence/ambiguity annotations.
    """
    llm = llm or get_llm()
    prompt = f"TRANSCRIPT:\n{transcript}"
    parsed = llm.structured(EXTRACTION_SCHEMA, prompt, system_prompt=EXTRACTION_SYSTEM)
    raw_items = parsed.get("items", []) if isinstance(parsed, dict) else []
    items = [to_action_item(it) for it in raw_items if isinstance(it, dict)]
    logger.debug("Extracted %d action item(s) from %s", len(items), source)
    return items


@tool(name="extractActionItems", description="Extract structured action items (task/owner/due date) from a meeting transcript.")
def extractActionItems(transcript: str) -> list[dict]:
    """Extract action items from a meeting transcript. Returns a list of dicts."""
    items = extract_action_items(transcript, llm=get_llm())
    return [i.model_dump(mode="json") for i in items]
