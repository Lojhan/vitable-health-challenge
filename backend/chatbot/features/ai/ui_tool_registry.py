"""Explicit mapping from tool names to frontend UI component kinds.

Tools listed here emit a ``9:`` (tool_result) protocol event that the
frontend renders as a structured component.  Tools *not* in this
registry are backend-only — their results are fed back to the LLM
silently and never surfaced as a UI component.
"""

from __future__ import annotations

from typing import Any

# tool_name → ui_kind (matches ChatMessage.MessageKind values)
UI_TOOL_MAP: dict[str, str] = {
    'show_providers_for_selection': 'providers',
    'check_availability': 'availability',
    'list_my_appointments': 'appointments',
}

TOOL_ACTIVITY_LABELS: dict[str, str] = {
    'show_providers_for_selection': 'Reviewing provider options',
    'check_availability': 'Checking appointment availability',
    'list_my_appointments': 'Loading your upcoming appointments',
    'book_appointment': 'Preparing your booking',
    'update_my_appointment': 'Updating your appointment',
    'cancel_my_appointment': 'Cancelling your appointment',
    'list_providers': 'Searching provider availability',
    'resolve_datetime_reference': 'Normalizing the requested time window',
    'calculate_visit_cost': 'Estimating visit coverage and cost',
}


def get_ui_kind(tool_name: str) -> str | None:
    """Return the UI kind for *tool_name*, or ``None`` if backend-only."""
    return UI_TOOL_MAP.get(tool_name)


def get_tool_activity_label(tool_name: str) -> str:
	"""Return a user-facing activity label for *tool_name*."""
	return TOOL_ACTIVITY_LABELS.get(tool_name, tool_name.replace('_', ' '))


def build_visible_tool_payload(
    *,
    tool_name: str,
    tool_call_id: str,
    state: str,
    result: object | None = None,
    error_message: str | None = None,
) -> dict[str, Any] | None:
    ui_kind = get_ui_kind(tool_name)
    if ui_kind is None:
        return None

    interaction_id = tool_call_id or f'{tool_name}-interaction'
    progress_message = get_tool_activity_label(tool_name)

    if ui_kind == 'providers':
        providers = []
        if isinstance(result, list):
            providers = result
        elif isinstance(result, dict) and isinstance(result.get('providers'), list):
            providers = result['providers']
        return {
            'type': 'providers',
            'interaction_id': interaction_id,
            'ui_state': state,
            'progress_message': progress_message,
            'error_message': error_message,
            'providers': providers,
        }

    if ui_kind == 'availability':
        payload: dict[str, Any] = {
            'type': 'availability',
            'interaction_id': interaction_id,
            'ui_state': state,
            'progress_message': progress_message,
            'error_message': error_message,
            'available_slots_utc': [],
        }
        if isinstance(result, dict):
            payload.update(result)
        return payload

    if ui_kind == 'appointments':
        payload = {
            'type': 'appointments',
            'interaction_id': interaction_id,
            'ui_state': state,
            'progress_message': progress_message,
            'error_message': error_message,
            'count': 0,
            'appointments': [],
        }
        if isinstance(result, dict):
            payload.update(result)
        return payload

    return {
        'type': ui_kind,
        'interaction_id': interaction_id,
        'ui_state': state,
        'progress_message': progress_message,
        'error_message': error_message,
        'data': result,
    }
