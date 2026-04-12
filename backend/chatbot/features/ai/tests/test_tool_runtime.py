import asyncio
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model

from chatbot.features.ai.application.runtime import ToolExecutionSandbox
from chatbot.features.ai.application.tool_runtime import ParsedToolCall, ToolExecutor
from chatbot.features.ai.base import BaseAgentInterface
from chatbot.features.ai.tool_registry import TOOL_EXECUTOR_BY_NAME
from chatbot.features.scheduling.models import Appointment


def _pk(instance: object) -> int:
    return cast(int, cast(Any, instance).pk)


def _build_tool_executor(*, user_id: int | None = None) -> ToolExecutor:
    return ToolExecutor(
        validator=BaseAgentInterface.validate_tool_arguments,
        executor_registry=TOOL_EXECUTOR_BY_NAME,
        user_id=user_id,
    )


def _build_sandbox() -> ToolExecutionSandbox:
    return ToolExecutionSandbox(
        max_tool_rounds=2,
        max_tool_calls=4,
        timeout_budget_ms=1000,
        per_tool_limit=2,
    )


@pytest.mark.django_db(transaction=True)
def test_tool_executor_lists_providers_from_parsed_tool_call(monkeypatch):
    from chatbot.features.scheduling.models import Provider

    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')
    Provider.objects.create(
        name='Dr. Alice Smith',
        specialty='General Practice',
        availability_dtstart=datetime(2026, 4, 10, 9, 0, 0, tzinfo=UTC),
        availability_rrule='FREQ=DAILY;BYHOUR=9,10,11;BYMINUTE=0;BYSECOND=0',
    )
    parsed_call = ParsedToolCall(
        tool_name='list_providers',
        arguments={},
        tool_call_id='tool-1',
    )

    result = asyncio.run(
        _build_tool_executor().execute(
            parsed_call,
            allowed_tools={'list_providers'},
            sandbox=_build_sandbox(),
        )
    )

    payload = cast(list[dict[str, object]], result.payload)
    names = {cast(str, provider['name']) for provider in payload}
    assert 'Dr. Alice Smith' in names
    assert all('provider_id' in provider and 'specialty' in provider for provider in payload)


@pytest.mark.django_db(transaction=True)
def test_tool_executor_passes_provider_id_to_check_availability(monkeypatch):
    from chatbot.features.scheduling.models import Provider

    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')
    provider = Provider.objects.create(
        name='Dr. Alice Smith',
        specialty='General Practice',
        availability_dtstart=datetime(2026, 4, 10, 9, 0, 0, tzinfo=UTC),
        availability_rrule='FREQ=DAILY;BYHOUR=9,10,11;BYMINUTE=0;BYSECOND=0',
    )
    parsed_call = ParsedToolCall(
        tool_name='check_availability',
        arguments={
            'date_range_str': '2026-04-10T09:00:00/2026-04-10T12:00:00',
            'provider_id': provider.pk,
        },
        tool_call_id='tool-2',
    )

    result = asyncio.run(
        _build_tool_executor().execute(
            parsed_call,
            allowed_tools={'check_availability'},
            sandbox=_build_sandbox(),
        )
    )

    payload = cast(dict[str, object], result.payload)
    assert payload['type'] == 'availability'
    assert payload['timezone'] == 'UTC'
    assert payload['availability_source'] == 'provider_rrule'
    assert payload['appointment_duration_note'] == '*Appointments last 1h.'
    assert payload['requested_window_start_utc'] == '2026-04-10T09:00:00'
    assert payload['requested_window_end_utc'] == '2026-04-10T12:00:00'
    assert payload['provider'] == {
        'provider_id': provider.pk,
        'name': 'Dr. Alice Smith',
        'specialty': 'General Practice',
    }
    assert payload['availability_dtstart_utc'] == '2026-04-10T09:00:00'
    assert payload['availability_rrule'] == 'FREQ=DAILY;BYHOUR=9,10,11;BYMINUTE=0;BYSECOND=0'
    assert payload['blocked_slots_utc'] == []


@pytest.mark.django_db(transaction=True)
def test_tool_executor_books_appointment_with_provider_id(monkeypatch):
    from chatbot.features.scheduling.models import Provider

    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='provider-dispatch-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )
    provider = Provider.objects.create(
        name='Dr. Alice Smith',
        specialty='General Practice',
        availability_dtstart=datetime(2026, 4, 10, 9, 0, 0, tzinfo=UTC),
        availability_rrule='FREQ=DAILY;BYHOUR=9,10,11;BYMINUTE=0;BYSECOND=0',
    )
    parsed_call = ParsedToolCall(
        tool_name='book_appointment',
        arguments={
            'time_slot': '2026-04-10T09:00:00',
            'symptoms_summary': 'Sore throat',
            'appointment_reason': 'Initial consult',
            'provider_id': provider.pk,
        },
        tool_call_id='tool-3',
    )

    result = asyncio.run(
        _build_tool_executor(user_id=_pk(user)).execute(
            parsed_call,
            allowed_tools={'book_appointment'},
            sandbox=_build_sandbox(),
        )
    )

    payload = cast(dict[str, object], result.payload)
    appointment_id = cast(int, payload['appointment_id'])
    booked = Appointment.objects.get(id=appointment_id)
    assert cast(Any, booked).provider_id == _pk(provider)


@pytest.mark.django_db(transaction=True)
def test_tool_executor_returns_validation_error_payload(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='validation-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )
    parsed_call = ParsedToolCall(
        tool_name='book_appointment',
        arguments={
            'time_slot': '2026-04-12T10:00:00',
            'symptoms_summary': '   ',
            'appointment_reason': '   ',
        },
        tool_call_id='tool-validation',
    )

    result = asyncio.run(
        _build_tool_executor(user_id=_pk(user)).execute(
            parsed_call,
            allowed_tools={'book_appointment'},
            sandbox=_build_sandbox(),
        )
    )

    payload = cast(dict[str, str], result.payload)
    assert payload['tool_name'] == 'book_appointment'
    assert 'Invalid arguments for tool call: book_appointment' in payload['error']
