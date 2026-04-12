import asyncio
import json
import os
from types import SimpleNamespace
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model

from chatbot.features.ai.base import (
    BaseAgentInterface,
    UserProfileSchema,
)
from chatbot.features.ai.openrouter_agent import OpenRouterAgent
from chatbot.features.chat.stream_protocol import (
    PREFIX_ERROR,
    PREFIX_FINISH,
    PREFIX_STATUS,
    PREFIX_TEXT_DELTA,
    PREFIX_TOOL_RESULT,
)
from chatbot.features.scheduling.models import Appointment


def _pk(instance: object) -> int:
    return cast(int, cast(Any, instance).pk)


def _parse_protocol_lines(lines: list[str]) -> list[tuple[str, Any]]:
    """Parse protocol-encoded lines into (prefix, payload) tuples."""
    result = []
    for line in lines:
        stripped = line.strip()
        if len(stripped) < 2 or stripped[1] != ':':
            result.append(('raw', stripped))
            continue
        prefix = stripped[0]
        try:
            payload = json.loads(stripped[2:])
        except (json.JSONDecodeError, IndexError):
            payload = stripped[2:]
        result.append((prefix, payload))
    return result


def _build_streaming_chunks(
    *,
    text_deltas: list[str] | None = None,
    tool_calls: list[dict] | None = None,
    finish_reason: str = 'stop',
) -> list[SimpleNamespace]:
    """Build a list of ChatCompletionChunk-like objects for streaming mock."""
    chunks = []
    for delta_text in (text_deltas or []):
        chunks.append(SimpleNamespace(
            choices=[SimpleNamespace(
                delta=SimpleNamespace(content=delta_text, tool_calls=None),
                finish_reason=None,
            )],
        ))

    if tool_calls:
        for i, tc in enumerate(tool_calls):
            # First chunk: id + name
            chunks.append(SimpleNamespace(
                choices=[SimpleNamespace(
                    delta=SimpleNamespace(
                        content=None,
                        tool_calls=[SimpleNamespace(
                            index=i,
                            id=tc.get('id', f'tc-{i}'),
                            function=SimpleNamespace(
                                name=tc.get('name', ''),
                                arguments='',
                            ),
                        )],
                    ),
                    finish_reason=None,
                )],
            ))
            # Second chunk: arguments
            chunks.append(SimpleNamespace(
                choices=[SimpleNamespace(
                    delta=SimpleNamespace(
                        content=None,
                        tool_calls=[SimpleNamespace(
                            index=i,
                            id=None,
                            function=SimpleNamespace(
                                name=None,
                                arguments=tc.get('arguments', '{}'),
                            ),
                        )],
                    ),
                    finish_reason=None,
                )],
            ))

    # Finish chunk
    chunks.append(SimpleNamespace(
        choices=[SimpleNamespace(
            delta=SimpleNamespace(content=None, tool_calls=None),
            finish_reason=finish_reason,
        )],
    ))
    return chunks


class FakeStreamingGateway:
    """A fake gateway that yields pre-built streaming chunks for each round."""

    def __init__(self, rounds: list[list[SimpleNamespace]]):
        self._rounds = list(rounds)
        self._round_index = 0
        self.calls = 0

    async def create_chat_completion(self, *, model, messages, tools, max_tokens):
        raise NotImplementedError('Use create_streaming_chat_completion')

    async def create_streaming_chat_completion(self, *, model, messages, tools, max_tokens):
        if self._round_index >= len(self._rounds):
            raise RuntimeError('No more streaming rounds configured')
        chunks = self._rounds[self._round_index]
        self._round_index += 1
        self.calls += 1
        for chunk in chunks:
            yield chunk


class RecordingStreamingGateway(FakeStreamingGateway):
    def __init__(self, rounds: list[list[SimpleNamespace]]):
        super().__init__(rounds=rounds)
        self.requests: list[dict[str, object]] = []

    async def create_streaming_chat_completion(self, *, model, messages, tools, max_tokens):
        self.requests.append(
            {
                'model': model,
                'messages': messages,
                'tools': tools,
                'max_tokens': max_tokens,
            }
        )
        async for chunk in super().create_streaming_chat_completion(
            model=model,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
        ):
            yield chunk


def _collect_streamed_lines(
    agent: OpenRouterAgent,
    prompt: str,
    history: list[dict[str, str]] | None = None,
) -> list[str]:
    async def _collect() -> list[str]:
        return [chunk async for chunk in agent.stream_response(prompt, history=history)]

    return asyncio.run(_collect())


def _collect_streamed_text(
    agent: OpenRouterAgent,
    prompt: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    parsed = _parse_protocol_lines(_collect_streamed_lines(agent, prompt, history=history))
    return ''.join(payload for prefix, payload in parsed if prefix == PREFIX_TEXT_DELTA)


def test_openrouter_agent_implements_base_interface():
    assert issubclass(OpenRouterAgent, BaseAgentInterface)


def test_openrouter_agent_requires_api_key_from_env(monkeypatch):
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)

    with pytest.raises(ValueError, match='OPENROUTER_API_KEY'):
        OpenRouterAgent()


def test_openrouter_agent_stream_response_returns_content(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')
    user_profile = UserProfileSchema(first_name='Jane', insurance_tier='Gold')

    gateway = RecordingStreamingGateway(
        rounds=[_build_streaming_chunks(text_deltas=['mocked-ai-response'])]
    )
    agent = OpenRouterAgent(
        model='openai/gpt-4o-mini',
        user_profile=user_profile,
        gateway=gateway,
    )

    result = _collect_streamed_text(agent, 'Hello there')

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

    assert len(gateway.requests) == 1
    call_kwargs = gateway.requests[0]
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

        async def create_streaming_chat_completion(self, *, model, messages, tools, max_tokens):
            self.calls.append(
                {
                    'model': model,
                    'messages': messages,
                    'tools': tools,
                    'max_tokens': max_tokens,
                }
            )
            for chunk in _build_streaming_chunks(text_deltas=['gateway-response']):
                yield chunk

    gateway = FakeGateway()
    agent = OpenRouterAgent(api_key='explicit-key', gateway=gateway)

    result = _collect_streamed_text(agent, 'Hello from gateway')

    assert result == 'gateway-response'
    assert len(gateway.calls) == 1
    assert gateway.calls[0]['messages'][1] == {'role': 'user', 'content': 'Hello from gateway'}


def test_openrouter_agent_refuses_out_of_scope_requests(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    class FailingGateway:
        def __init__(self):
            self.calls = 0

        async def create_streaming_chat_completion(self, **kwargs):
            self.calls += 1
            raise RuntimeError('should not be called')
            yield

    gateway = FailingGateway()
    agent = OpenRouterAgent(model='openai/gpt-4o-mini', gateway=gateway)

    result = _collect_streamed_text(agent, 'write a bubble sort in python')

    assert result == OpenRouterAgent.OUT_OF_SCOPE_RESPONSE
    assert gateway.calls == 0


def test_stream_response_source_does_not_toggle_async_unsafe_env():
    source = OpenRouterAgent.stream_response.__code__.co_names
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
    result = _collect_streamed_text(agent, 'I have severe chest pain')

    assert agent.backend_catches_emergency_override(result) is True


@pytest.mark.django_db(transaction=True)
def test_stream_response_resolves_tools_before_yielding(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    # Round 1: tool call to check_availability
    round1 = _build_streaming_chunks(
        tool_calls=[{
            'id': 'tool-call-1',
            'name': 'check_availability',
            'arguments': json.dumps({'date_range_str': '2026-04-12T09:00:00/2026-04-12T11:00:00'}),
        }],
    )
    # Round 2: text response
    round2 = _build_streaming_chunks(text_deltas=['Here are available slots.'])

    gateway = FakeStreamingGateway(rounds=[round1, round2])
    agent = OpenRouterAgent(api_key='test-key', gateway=gateway)

    async def collect_chunks():
        return [chunk async for chunk in agent.stream_response(
            'tomorrow morning',
            history=[{'role': 'user', 'content': 'I have a sore throat'}],
        )]

    streamed = asyncio.run(collect_chunks())
    parsed = _parse_protocol_lines(streamed)

    # Should have: status, tool_result (availability), text_delta, finish
    prefixes = [p for p, _ in parsed]
    assert PREFIX_STATUS in prefixes
    assert PREFIX_TOOL_RESULT in prefixes
    assert PREFIX_TEXT_DELTA in prefixes
    assert PREFIX_FINISH in prefixes

    # Check tool_result has availability data
    tool_results = [(p, v) for p, v in parsed if p == PREFIX_TOOL_RESULT]
    assert len(tool_results) >= 1
    assert tool_results[0][1]['ui_kind'] == 'availability'
    assert tool_results[0][1]['result']['type'] == 'availability'
    assert tool_results[0][1]['result']['availability_source'] == 'open_slots'
    assert isinstance(tool_results[0][1]['result']['available_slots_utc'], list)

    assert gateway.calls == 2


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

    gateway = RecordingStreamingGateway(
        rounds=[
            _build_streaming_chunks(
                tool_calls=[
                    {
                        'id': 'tool-call-1',
                        'name': 'check_availability',
                        'arguments': json.dumps(
                            {
                                'date_range_str': '2026-04-12T09:00:00/2026-04-12T11:00:00'
                            }
                        ),
                    },
                    {
                        'id': 'tool-call-2',
                        'name': 'book_appointment',
                        'arguments': json.dumps(
                            {
                                'time_slot': '2026-04-12T10:00:00',
                                'rrule_str': 'FREQ=DAILY;COUNT=1',
                                'symptoms_summary': 'Sore throat and fatigue',
                                'appointment_reason': 'Needs in-person assessment',
                            }
                        ),
                    },
                ]
            ),
            _build_streaming_chunks(text_deltas=['Appointment confirmed']),
        ]
    )
    agent = OpenRouterAgent(model='openai/gpt-4o-mini', user_id=_pk(user), gateway=gateway)

    result = _collect_streamed_text(agent, 'Schedule me for tomorrow morning')

    assert result == 'Appointment confirmed'
    assert gateway.calls == 2
    assert Appointment.objects.filter(user_id=_pk(user)).count() == 1

    second_call_messages = cast(list[dict[str, object]], gateway.requests[1]['messages'])
    tool_messages = [message for message in second_call_messages if message.get('role') == 'tool']
    assert len(tool_messages) == 2

    booking_tool_payload = json.loads(tool_messages[1]['content'])
    assert booking_tool_payload['appointment_id'] > 0
    assert booking_tool_payload['time_slot_utc'].startswith('2026-04-12T10:00:00')
    assert booking_tool_payload['time_slot_human_utc'] == 'Sunday, April 12, 2026 at 10:00 AM UTC'


def test_stream_response_emits_text_deltas_token_by_token(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    chunks = _build_streaming_chunks(text_deltas=['Hello', ' there', '.'])
    gateway = FakeStreamingGateway(rounds=[chunks])
    agent = OpenRouterAgent(api_key='test-key', gateway=gateway)

    async def collect_chunks():
        return [chunk async for chunk in agent.stream_response('hello')]

    streamed = asyncio.run(collect_chunks())
    parsed = _parse_protocol_lines(streamed)

    text_deltas = [v for p, v in parsed if p == PREFIX_TEXT_DELTA]
    assert text_deltas == ['Hello', ' there', '.']
    assert parsed[-1][0] == PREFIX_FINISH


@pytest.mark.django_db(transaction=True)
def test_stream_response_keeps_list_providers_silent(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    round1 = _build_streaming_chunks(
        tool_calls=[{
            'id': 'tool-call-1',
            'name': 'list_providers',
            'arguments': '{}',
        }],
    )
    # Round 2: text response after tool result
    round2 = _build_streaming_chunks(text_deltas=['Here are the providers.'])

    gateway = FakeStreamingGateway(rounds=[round1, round2])
    agent = OpenRouterAgent(api_key='test-key', gateway=gateway)

    async def collect_chunks():
        return [chunk async for chunk in agent.stream_response('show providers')]

    streamed = asyncio.run(collect_chunks())
    parsed = _parse_protocol_lines(streamed)

    tool_results = [(p, v) for p, v in parsed if p == PREFIX_TOOL_RESULT]
    assert tool_results == []

    text_deltas = [v for p, v in parsed if p == PREFIX_TEXT_DELTA]
    assert text_deltas == ['Here are the providers.']


@pytest.mark.django_db(transaction=True)
def test_stream_response_emits_tool_result_for_visible_provider_tool(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    round1 = _build_streaming_chunks(
        tool_calls=[{
            'id': 'tool-call-1',
            'name': 'show_providers_for_selection',
            'arguments': '{}',
        }],
    )
    round2 = _build_streaming_chunks(text_deltas=['Here are the providers.'])

    gateway = FakeStreamingGateway(rounds=[round1, round2])
    agent = OpenRouterAgent(api_key='test-key', gateway=gateway)

    async def collect_chunks():
        return [chunk async for chunk in agent.stream_response('show providers')]

    streamed = asyncio.run(collect_chunks())
    parsed = _parse_protocol_lines(streamed)

    tool_results = [(p, v) for p, v in parsed if p == PREFIX_TOOL_RESULT]
    assert len(tool_results) >= 1
    assert tool_results[0][1]['ui_kind'] == 'providers'
    assert isinstance(tool_results[0][1]['result'], list)


def test_stream_response_returns_fallback_text_on_provider_error(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    class FailingGateway:
        async def create_streaming_chat_completion(self, **kwargs):
            _ = kwargs
            raise RuntimeError('provider unavailable')
            if False:
                yield None

    agent = OpenRouterAgent(api_key='test-key', gateway=FailingGateway())

    async def collect_chunks():
        return [chunk async for chunk in agent.stream_response('hello')]

    streamed = asyncio.run(collect_chunks())
    parsed = _parse_protocol_lines(streamed)

    error_events = [v for p, v in parsed if p == PREFIX_ERROR]
    assert len(error_events) == 1
    assert 'could not process' in error_events[0].lower()


def test_stream_response_logs_provider_error(monkeypatch, caplog):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    class FailingGateway:
        async def create_streaming_chat_completion(self, **kwargs):
            _ = kwargs
            raise RuntimeError('provider unavailable')
            if False:
                yield None

    agent = OpenRouterAgent(api_key='test-key', gateway=FailingGateway())

    async def collect_chunks():
        return [chunk async for chunk in agent.stream_response('hello')]

    with caplog.at_level('ERROR'):
        streamed = asyncio.run(collect_chunks())

    parsed = _parse_protocol_lines(streamed)
    error_events = [v for p, v in parsed if p == PREFIX_ERROR]
    assert len(error_events) == 1
    assert 'ai.stream_response.failed' in caplog.text


def test_stream_response_uses_configured_max_tool_rounds(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    gateway = RecordingStreamingGateway(
        rounds=[
            _build_streaming_chunks(
                tool_calls=[
                    {
                        'id': 'tool-call-1',
                        'name': 'calculate_visit_cost',
                        'arguments': json.dumps(
                            {'insurance_tier': 'Gold', 'visit_type': 'virtual'}
                        ),
                    }
                ]
            ),
            _build_streaming_chunks(
                tool_calls=[
                    {
                        'id': 'tool-call-2',
                        'name': 'calculate_visit_cost',
                        'arguments': json.dumps(
                            {'insurance_tier': 'Gold', 'visit_type': 'virtual'}
                        ),
                    }
                ]
            ),
        ]
    )
    agent = OpenRouterAgent(
        api_key='explicit-key',
        max_tool_rounds=2,
        gateway=gateway,
    )

    result = _collect_streamed_text(agent, 'schedule a visit')

    assert gateway.calls == 2
    assert 'multiple tool steps' in result


def test_stream_response_stops_when_tool_call_budget_is_exceeded(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    agent = OpenRouterAgent(
        api_key='explicit-key',
        max_tool_calls=2,
        gateway=RecordingStreamingGateway(
            rounds=[
                _build_streaming_chunks(
                    tool_calls=[
                        {
                            'id': 'tool-call-1',
                            'name': 'calculate_visit_cost',
                            'arguments': json.dumps(
                                {'insurance_tier': 'Gold', 'visit_type': 'virtual'}
                            ),
                        },
                        {
                            'id': 'tool-call-2',
                            'name': 'calculate_visit_cost',
                            'arguments': json.dumps(
                                {'insurance_tier': 'Gold', 'visit_type': 'virtual'}
                            ),
                        },
                        {
                            'id': 'tool-call-3',
                            'name': 'calculate_visit_cost',
                            'arguments': json.dumps(
                                {'insurance_tier': 'Gold', 'visit_type': 'virtual'}
                            ),
                        },
                    ]
                )
            ]
        ),
    )

    result = _collect_streamed_text(agent, 'schedule a visit')

    assert 'tool call budget' in result


def test_stream_response_does_not_inject_authenticated_name(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    user_profile = UserProfileSchema(first_name='Jane', insurance_tier='Gold')
    agent = OpenRouterAgent(
        model='openai/gpt-4o-mini',
        user_profile=user_profile,
        gateway=RecordingStreamingGateway(
            rounds=[
                _build_streaming_chunks(
                    text_deltas=['Let us schedule your visit for tomorrow.']
                )
            ]
        ),
    )

    result = _collect_streamed_text(agent, 'Please help me book a visit')

    assert result == 'Let us schedule your visit for tomorrow.'
    assert '$20.00' not in result


def test_stream_response_greeting_does_not_force_cost(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    user_profile = UserProfileSchema(first_name='Jane', insurance_tier='Gold')
    agent = OpenRouterAgent(
        model='openai/gpt-4o-mini',
        user_profile=user_profile,
        gateway=RecordingStreamingGateway(
            rounds=[
                _build_streaming_chunks(
                    text_deltas=['Hello there! How can I assist you today?']
                )
            ]
        ),
    )

    result = _collect_streamed_text(agent, 'hey!')

    assert result == 'Hello there! How can I assist you today?'
    assert '$20.00' not in result


def test_stream_response_does_not_mutate_emergency_override(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    user_profile = UserProfileSchema(first_name='Jane', insurance_tier='Gold')
    agent = OpenRouterAgent(model='openai/gpt-4o-mini', user_profile=user_profile)

    result = _collect_streamed_text(agent, 'I have chest pain and cannot breathe')

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

    gateway = RecordingStreamingGateway(
        rounds=[
            _build_streaming_chunks(
                tool_calls=[
                    {
                        'id': 'tool-call-1',
                        'name': 'resolve_datetime_reference',
                        'arguments': json.dumps(
                            {'datetime_reference': 'next monday 09:00 UTC'}
                        ),
                    }
                ]
            ),
            _build_streaming_chunks(
                tool_calls=[
                    {
                        'id': 'tool-call-2',
                        'name': 'book_appointment',
                        'arguments': json.dumps(
                            {
                                'time_slot': '2026-04-13T09:00:00',
                                'symptoms_summary': 'Sore throat, fever and cough',
                                'appointment_reason': 'Evaluate persistent fever',
                            }
                        ),
                    }
                ]
            ),
            _build_streaming_chunks(
                text_deltas=['Appointment confirmed for next Monday.']
            ),
        ]
    )
    agent = OpenRouterAgent(model='openai/gpt-4o-mini', user_id=_pk(user), gateway=gateway)

    result = _collect_streamed_text(
        agent,
        'Book next monday 09:00 with my symptoms context',
    )

    assert result == 'Appointment confirmed for next Monday.'
    assert gateway.calls == 3
    assert Appointment.objects.filter(user_id=_pk(user)).count() == 1


def test_list_providers_tool_is_registered_in_get_tools():
    tools = OpenRouterAgent.get_tools()
    tool_names = {tool['function']['name'] for tool in tools}
    assert 'list_providers' in tool_names
    assert 'show_providers_for_selection' in tool_names


