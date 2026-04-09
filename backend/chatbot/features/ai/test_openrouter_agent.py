import asyncio
import json
import os
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
    assert 'Current UTC datetime is' in expected_system_prompt
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
    assert 'Current UTC datetime is' in call_kwargs['messages'][0]['content']
    assert call_kwargs['messages'][1] == {'role': 'user', 'content': 'Hello there'}
    assert call_kwargs['tools'] == OpenRouterAgent.get_tools()


def test_openrouter_agent_accepts_explicit_api_key_without_env(monkeypatch):
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)

    agent = OpenRouterAgent(api_key='explicit-key')

    assert agent._api_key == 'explicit-key'
    assert os.getenv('OPENROUTER_API_KEY') is None


def test_openrouter_agent_refuses_out_of_scope_requests(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    agent = OpenRouterAgent(model='openai/gpt-4o-mini')
    mocked_create = AsyncMock()
    agent._client.chat.completions.create = mocked_create

    result = asyncio.run(agent.generate_response('write a bubble sort in python'))

    assert result == OpenRouterAgent.OUT_OF_SCOPE_RESPONSE
    mocked_create.assert_not_awaited()


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
