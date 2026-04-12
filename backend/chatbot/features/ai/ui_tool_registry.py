"""Explicit mapping from tool names to frontend UI component kinds.

Tools listed here emit a ``9:`` (tool_result) protocol event that the
frontend renders as a structured component.  Tools *not* in this
registry are backend-only — their results are fed back to the LLM
silently and never surfaced as a UI component.
"""

from __future__ import annotations

# tool_name → ui_kind (matches ChatMessage.MessageKind values)
UI_TOOL_MAP: dict[str, str] = {
    'list_providers': 'providers',
    'check_availability': 'availability',
    'list_my_appointments': 'appointments',
}


def get_ui_kind(tool_name: str) -> str | None:
    """Return the UI kind for *tool_name*, or ``None`` if backend-only."""
    return UI_TOOL_MAP.get(tool_name)
