import asyncio
import inspect
import json
import os
from datetime import UTC
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from django.contrib.auth import get_user_model

from chatbot.features.ai.base import (
    BaseAgentInterface,
    UserProfileSchema,
)
from chatbot.features.ai.openrouter_agent import OpenRouterAgent
from chatbot.features.scheduling.models import Appointment


def _pk(instance: object) -> int:
    return cast(int, cast(Any, instance).pk)


def test_openrouter_agent_implements_base_interface():
    assert issubclass(OpenRouterAgent, BaseAgentInterface)


def test_openrouter_agent_requires_api_key_from_env(monkeypatch):
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)

    with pytest.raises(ValueError, match='OPENROUTER_API_KEY'):
        OpenRouterAgent()


def test_openrouter_agent_generate_response_returns_content(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')
    user_profile = UserProfileSchema(first_name='Jane', insurance_tier='Gold')

    agent = OpenRouterAgent(model='openai/gpt-4o-mini', user_profile=user_profile)
    mocked_create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='mocked-ai-response')
                )
            ]
        )
    )
    agent._client.chat.completions.create = mocked_create

    result = asyncio.run(agent.generate_response('Hello there'))

    assert result == 'mocked-ai-response'
    assert '$20.00' not in result
    expected_system_prompt = agent._build_system_prompt()
    assert 'Manchester Triage System' in expected_system_prompt
    assert 'Do not diagnose' in expected_system_prompt
    assert '<EMERGENCY_OVERRIDE>' in expected_system_prompt
    assert 'TEMPORAL ANCHORS' in expected_system_prompt
    assert 'Jane' in expected_system_prompt
    assert 'Gold' in expected_system_prompt
    assert 'Explicitly mention the user first name somewhere in the response' in expected_system_prompt
    assert 'For scheduling, availability, booking, rescheduling, cancellation' in expected_system_prompt
    assert 'call calculate_visit_cost exactly once' in expected_system_prompt
    assert 'Do not mention the estimated cost on a pure greeting' in expected_system_prompt

    mocked_create.assert_awaited_once()
    assert mocked_create.await_args is not None
    call_kwargs = mocked_create.await_args.kwargs
    assert call_kwargs['model'] == 'openai/gpt-4o-mini'
    assert call_kwargs['messages'][0]['role'] == 'system'
    assert 'TEMPORAL ANCHORS' in call_kwargs['messages'][0]['content']
    assert call_kwargs['messages'][1] == {'role': 'user', 'content': 'Hello there'}
    assert call_kwargs['tools'] == OpenRouterAgent.get_tools()


def test_openrouter_agent_accepts_explicit_api_key_without_env(monkeypatch):
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)

    agent = OpenRouterAgent(api_key='explicit-key')

    assert agent._api_key == 'explicit-key'
    assert os.getenv('OPENROUTER_API_KEY') is None


def test_openrouter_agent_can_use_injected_gateway_without_client_calls(monkeypatch):
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)

    class FakeGateway:
        def __init__(self):
            self.calls = []

        async def create_chat_completion(self, *, model, messages, tools, max_tokens):
            self.calls.append(
                {
                    'model': model,
                    'messages': messages,
                    'tools': tools,
                    'max_tokens': max_tokens,
                }
            )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='gateway-response'))]
            )

    gateway = FakeGateway()
    agent = OpenRouterAgent(api_key='explicit-key', gateway=gateway)

    result = asyncio.run(agent.generate_response('Hello from gateway'))

    assert result == 'gateway-response'
    assert len(gateway.calls) == 1
    assert gateway.calls[0]['messages'][1] == {'role': 'user', 'content': 'Hello from gateway'}


def test_openrouter_agent_refuses_out_of_scope_requests(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    agent = OpenRouterAgent(model='openai/gpt-4o-mini')
    mocked_create = AsyncMock()
    agent._client.chat.completions.create = mocked_create

    result = asyncio.run(agent.generate_response('write a bubble sort in python'))

    assert result == OpenRouterAgent.OUT_OF_SCOPE_RESPONSE
    mocked_create.assert_not_awaited()


def test_generate_response_source_does_not_toggle_async_unsafe_env():
    source = inspect.getsource(OpenRouterAgent.generate_response)
    assert 'DJANGO_ALLOW_ASYNC_UNSAFE' not in source


def test_openrouter_agent_registers_calculate_visit_cost_tool_schema():
    tools = OpenRouterAgent.get_tools()

    tool_names = {tool['function']['name'] for tool in tools}

    assert 'calculate_visit_cost' in tool_names
    assert 'resolve_datetime_reference' in tool_names
    assert 'check_availability' in tool_names
    assert 'book_appointment' in tool_names
    assert 'list_my_appointments' in tool_names
    assert 'cancel_my_appointment' in tool_names
    assert 'update_my_appointment' in tool_names


def test_backend_catches_emergency_override_tag(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    agent = OpenRouterAgent(model='openai/gpt-4o-mini')
    mocked_create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='<EMERGENCY_OVERRIDE>')
                )
            ]
        )
    )
    agent._client.chat.completions.create = mocked_create

    result = asyncio.run(agent.generate_response('I have severe chest pain'))

    assert agent.backend_catches_emergency_override(result) is True


@pytest.mark.django_db(transaction=True)
def test_stream_response_resolves_tools_before_yielding(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    agent = OpenRouterAgent(model='openai/gpt-4o-mini')
    first_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='',
                    tool_calls=[
                        SimpleNamespace(
                            id='tool-call-1',
                            function=SimpleNamespace(
                                name='check_availability',
                                arguments=json.dumps(
                                    {
                                        'date_range_str': (
                                            '2026-04-12T09:00:00/2026-04-12T11:00:00'
                                        )
                                    }
                                ),
                            ),
                        )
                    ],
                )
            )
        ]
    )
    second_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content='Here are available slots.')
            )
        ]
    )

    mocked_create = AsyncMock(side_effect=[first_response, second_response])
    agent._client.chat.completions.create = mocked_create

    async def collect_chunks():
        return [
            chunk
            async for chunk in agent.stream_response(
                'tomorrow morning',
                history=[{'role': 'user', 'content': 'I have a sore throat'}],
            )
        ]

    streamed_chunks = asyncio.run(collect_chunks())

    assert streamed_chunks == ['Here are available slots.']
    assert mocked_create.await_count == 2


@pytest.mark.django_db(transaction=True)
def test_openrouter_agent_integration_executes_scheduling_tools(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='integration-user',
        password='safe-password-123',
        insurance_tier='Bronze',
        medical_history={},
    )

    agent = OpenRouterAgent(model='openai/gpt-4o-mini', user_id=_pk(user))

    first_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='',
                    tool_calls=[
                        SimpleNamespace(
                            id='tool-call-1',
                            function=SimpleNamespace(
                                name='check_availability',
                                arguments=json.dumps(
                                    {
                                        'date_range_str': (
                                            '2026-04-12T09:00:00/2026-04-12T11:00:00'
                                        )
                                    }
                                ),
                            ),
                        ),
                        SimpleNamespace(
                            id='tool-call-2',
                            function=SimpleNamespace(
                                name='book_appointment',
                                arguments=json.dumps(
                                    {
                                        'time_slot': '2026-04-12T10:00:00',
                                        'rrule_str': 'FREQ=DAILY;COUNT=1',
                                        'symptoms_summary': 'Sore throat and fatigue',
                                        'appointment_reason': 'Needs in-person assessment',
                                    }
                                ),
                            ),
                        ),
                    ],
                )
            )
        ]
    )

    second_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content='Appointment confirmed')
            )
        ]
    )

    mocked_create = AsyncMock(side_effect=[first_response, second_response])
    agent._client.chat.completions.create = mocked_create

    result = asyncio.run(agent.generate_response('Schedule me for tomorrow morning'))

    assert result == 'Appointment confirmed'
    assert mocked_create.await_count == 2
    assert Appointment.objects.filter(user_id=_pk(user)).count() == 1

    second_call_messages = mocked_create.await_args_list[1].kwargs['messages']
    tool_messages = [message for message in second_call_messages if message.get('role') == 'tool']
    assert len(tool_messages) == 2

    booking_tool_payload = json.loads(tool_messages[1]['content'])
    assert booking_tool_payload['appointment_id'] > 0
    assert booking_tool_payload['time_slot_utc'].startswith('2026-04-12T10:00:00')
    assert booking_tool_payload['time_slot_human_utc'] == 'Sunday, April 12, 2026 at 10:00 AM UTC'


def test_stream_response_splits_multiple_message_blocks(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    agent = OpenRouterAgent(model='openai/gpt-4o-mini')
    mocked_create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='First message.<MESSAGE_BREAK>Second message.'
                    )
                )
            ]
        )
    )
    agent._client.chat.completions.create = mocked_create

    async def collect_chunks():
        return [chunk async for chunk in agent.stream_response('hello')]

    streamed_chunks = asyncio.run(collect_chunks())

    assert streamed_chunks == ['First message.', 'Second message.']


def test_stream_response_returns_fallback_text_on_provider_error(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    agent = OpenRouterAgent(model='openai/gpt-4o-mini')
    agent._client.chat.completions.create = AsyncMock(
        side_effect=RuntimeError('provider unavailable')
    )

    async def collect_chunks():
        return [chunk async for chunk in agent.stream_response('hello')]

    streamed_chunks = asyncio.run(collect_chunks())

    assert streamed_chunks == ['I could not process your request right now. Please try again.']


def test_stream_response_logs_provider_error(monkeypatch, caplog):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    agent = OpenRouterAgent(model='openai/gpt-4o-mini')
    agent._client.chat.completions.create = AsyncMock(
        side_effect=RuntimeError('provider unavailable')
    )

    async def collect_chunks():
        return [chunk async for chunk in agent.stream_response('hello')]

    with caplog.at_level('ERROR'):
        streamed_chunks = asyncio.run(collect_chunks())

    assert streamed_chunks == ['I could not process your request right now. Please try again.']
    assert 'ai.stream_response.failed' in caplog.text


def test_generate_response_uses_configured_max_tool_rounds(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    looping_tool_call = SimpleNamespace(
        id='tool-call-1',
        function=SimpleNamespace(
            name='calculate_visit_cost',
            arguments=json.dumps({'insurance_tier': 'Gold', 'visit_type': 'virtual'}),
        ),
    )

    class FakeGateway:
        def __init__(self):
            self.calls = 0

        async def create_chat_completion(self, *, model, messages, tools, max_tokens):
            _ = (model, messages, tools, max_tokens)
            self.calls += 1
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='', tool_calls=[looping_tool_call])
                    )
                ]
            )

    gateway = FakeGateway()
    agent = OpenRouterAgent(
        api_key='explicit-key',
        max_tool_rounds=2,
        gateway=gateway,
    )

    result = asyncio.run(agent.generate_response('schedule a visit'))

    assert gateway.calls == 2
    assert 'multiple tool steps' in result


def test_generate_response_stops_when_tool_call_budget_is_exceeded(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    tool_calls = [
        SimpleNamespace(
            id='tool-call-1',
            function=SimpleNamespace(
                name='calculate_visit_cost',
                arguments=json.dumps({'insurance_tier': 'Gold', 'visit_type': 'virtual'}),
            ),
        ),
        SimpleNamespace(
            id='tool-call-2',
            function=SimpleNamespace(
                name='calculate_visit_cost',
                arguments=json.dumps({'insurance_tier': 'Gold', 'visit_type': 'virtual'}),
            ),
        ),
        SimpleNamespace(
            id='tool-call-3',
            function=SimpleNamespace(
                name='calculate_visit_cost',
                arguments=json.dumps({'insurance_tier': 'Gold', 'visit_type': 'virtual'}),
            ),
        ),
    ]

    class FakeGateway:
        async def create_chat_completion(self, *, model, messages, tools, max_tokens):
            _ = (model, messages, tools, max_tokens)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='', tool_calls=tool_calls)
                    )
                ]
            )

    agent = OpenRouterAgent(
        api_key='explicit-key',
        max_tool_calls=2,
        gateway=FakeGateway(),
    )

    result = asyncio.run(agent.generate_response('schedule a visit'))

    assert 'tool call budget' in result


def test_generate_response_logs_start_and_completion(monkeypatch, caplog):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    class FakeGateway:
        async def create_chat_completion(self, *, model, messages, tools, max_tokens):
            _ = (model, messages, tools, max_tokens)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='final answer', tool_calls=[])
                    )
                ]
            )

    agent = OpenRouterAgent(
        api_key='explicit-key',
        gateway=FakeGateway(),
    )

    with caplog.at_level('INFO'):
        result = asyncio.run(agent.generate_response('hello'))

    assert result == 'final answer'
    assert 'ai.generate_response.started' in caplog.text
    assert 'ai.generate_response.completed' in caplog.text


def test_generate_response_does_not_inject_authenticated_name(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    user_profile = UserProfileSchema(first_name='Jane', insurance_tier='Gold')
    agent = OpenRouterAgent(model='openai/gpt-4o-mini', user_profile=user_profile)
    agent._client.chat.completions.create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='Let us schedule your visit for tomorrow.')
                )
            ]
        )
    )

    result = asyncio.run(agent.generate_response('Please help me book a visit'))

    assert result == 'Let us schedule your visit for tomorrow.'
    assert '$20.00' not in result


def test_generate_response_greeting_does_not_force_cost(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    user_profile = UserProfileSchema(first_name='Jane', insurance_tier='Gold')
    agent = OpenRouterAgent(model='openai/gpt-4o-mini', user_profile=user_profile)
    agent._client.chat.completions.create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='Hello there! How can I assist you today?')
                )
            ]
        )
    )

    result = asyncio.run(agent.generate_response('hey!'))

    assert result == 'Hello there! How can I assist you today?'
    assert '$20.00' not in result


def test_generate_response_does_not_mutate_emergency_override(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    user_profile = UserProfileSchema(first_name='Jane', insurance_tier='Gold')
    agent = OpenRouterAgent(model='openai/gpt-4o-mini', user_profile=user_profile)
    agent._client.chat.completions.create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content='<EMERGENCY_OVERRIDE>'))
            ]
        )
    )

    result = asyncio.run(agent.generate_response('I have chest pain and cannot breathe'))

    assert result == '<EMERGENCY_OVERRIDE>'


@pytest.mark.django_db(transaction=True)
def test_openrouter_agent_handles_multi_round_chained_tool_calls(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='chain-tools-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )

    agent = OpenRouterAgent(model='openai/gpt-4o-mini', user_id=_pk(user))

    first_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            id='tool-call-1',
                            function=SimpleNamespace(
                                name='resolve_datetime_reference',
                                arguments=json.dumps(
                                    {'datetime_reference': 'next monday 09:00 UTC'}
                                ),
                            ),
                        )
                    ],
                )
            )
        ]
    )
    second_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            id='tool-call-2',
                            function=SimpleNamespace(
                                name='book_appointment',
                                arguments=json.dumps(
                                    {
                                        'time_slot': '2026-04-13T09:00:00',
                                        'symptoms_summary': 'Sore throat, fever and cough',
                                        'appointment_reason': 'Evaluate persistent fever',
                                    }
                                ),
                            ),
                        )
                    ],
                )
            )
        ]
    )
    third_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content='Appointment confirmed for next Monday.')
            )
        ]
    )

    mocked_create = AsyncMock(
        side_effect=[first_response, second_response, third_response]
    )
    agent._client.chat.completions.create = mocked_create

    result = asyncio.run(
        agent.generate_response('Book next monday 09:00 with my symptoms context')
    )

    assert result == 'Appointment confirmed for next Monday.'
    assert mocked_create.await_count == 3
    assert Appointment.objects.filter(user_id=_pk(user)).count() == 1


# ── Provider tool dispatch T17-T19 ────────────────────────────────────────────


# T17
@pytest.mark.django_db
def test_execute_tool_call_list_providers_returns_provider_list(monkeypatch):
    from chatbot.features.scheduling.models import Provider

    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')
    Provider.objects.create(
        name='Dr. Alice Smith',
        specialty='General Practice',
        availability_dtstart=__import__('datetime').datetime(2026, 4, 10, 9, 0, 0, tzinfo=UTC),
        availability_rrule='FREQ=DAILY;BYHOUR=9,10,11;BYMINUTE=0;BYSECOND=0',
    )

    agent = OpenRouterAgent(model='openai/gpt-4o-mini')
    tool_call = SimpleNamespace(
        id='tool-1',
        function=SimpleNamespace(name='list_providers', arguments='{}'),
    )

    result = agent._execute_tool_call(tool_call)

    assert isinstance(result, list)
    # 5 seeded providers + 1 newly created = at least 1 with the target name
    names = {p['name'] for p in result}
    assert 'Dr. Alice Smith' in names
    assert all('provider_id' in p and 'specialty' in p for p in result)


# T18
@pytest.mark.django_db
def test_execute_tool_call_check_availability_passes_provider_id(monkeypatch):
    from chatbot.features.scheduling.models import Provider

    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')
    provider = Provider.objects.create(
        name='Dr. Alice Smith',
        specialty='General Practice',
        availability_dtstart=__import__('datetime').datetime(2026, 4, 10, 9, 0, 0, tzinfo=UTC),
        availability_rrule='FREQ=DAILY;BYHOUR=9,10,11;BYMINUTE=0;BYSECOND=0',
    )

    agent = OpenRouterAgent(model='openai/gpt-4o-mini')
    tool_call = SimpleNamespace(
        id='tool-2',
        function=SimpleNamespace(
            name='check_availability',
            arguments=json.dumps({
                'date_range_str': '2026-04-10T09:00:00/2026-04-10T12:00:00',
                'provider_id': provider.pk,
            }),
        ),
    )

    result = agent._execute_tool_call(tool_call)

    assert isinstance(result, dict)
    assert result['total_slots'] == 3
    assert result['timezone'] == 'UTC'
    assert result['appointment_duration_note'] == '*Appointments last 1h.'
    assert result['summary_lines'] == ['Friday, April 10 (Morning): 9:00 AM - 12:00 PM']
    assert result['grouped_human_utc'] == [
        {
            'day_iso_utc': '2026-04-10',
            'day': 'Friday, April 10',
            'period': 'morning',
            'windows_utc': ['9:00 AM - 12:00 PM'],
            'slot_count': 3,
        }
    ]


# T19
@pytest.mark.django_db(transaction=True)
def test_execute_tool_call_book_appointment_passes_provider_id(monkeypatch):
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
        availability_dtstart=__import__('datetime').datetime(2026, 4, 10, 9, 0, 0, tzinfo=UTC),
        availability_rrule='FREQ=DAILY;BYHOUR=9,10,11;BYMINUTE=0;BYSECOND=0',
    )

    agent = OpenRouterAgent(model='openai/gpt-4o-mini', user_id=_pk(user))
    tool_call = SimpleNamespace(
        id='tool-3',
        function=SimpleNamespace(
            name='book_appointment',
            arguments=json.dumps({
                'time_slot': '2026-04-10T09:00:00',
                'symptoms_summary': 'Sore throat',
                'appointment_reason': 'Initial consult',
                'provider_id': provider.pk,
            }),
        ),
    )

    result = agent._execute_tool_call(tool_call)
    typed_result = cast(dict[str, Any], result)

    assert typed_result['appointment_id'] > 0
    booked = Appointment.objects.get(id=typed_result['appointment_id'])
    assert cast(Any, booked).provider_id == _pk(provider)


def test_list_providers_tool_is_registered_in_get_tools():
    tools = OpenRouterAgent.get_tools()
    tool_names = {tool['function']['name'] for tool in tools}
    assert 'list_providers' in tool_names


@pytest.mark.django_db(transaction=True)
def test_execute_tool_call_rejects_blank_booking_fields(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='validation-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )

    agent = OpenRouterAgent(model='openai/gpt-4o-mini', user_id=_pk(user))
    tool_call = SimpleNamespace(
        id='tool-validation',
        function=SimpleNamespace(
            name='book_appointment',
            arguments=json.dumps(
                {
                    'time_slot': '2026-04-12T10:00:00',
                    'symptoms_summary': '   ',
                    'appointment_reason': '   ',
                }
            ),
        ),
    )

    with pytest.raises(ValueError, match='book_appointment'):
        agent._execute_tool_call(tool_call)
