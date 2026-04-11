import asyncio
import json
from types import SimpleNamespace

from chatbot.features.ai.infrastructure.gateway import GatewayCircuitBreaker, ResilientGateway
from chatbot.features.ai.openrouter_agent import OpenRouterAgent


class _FakeGateway:
    def __init__(self, responses=None, error: Exception | None = None):
        self.calls = 0
        self._responses = responses or []
        self._error = error

    async def create_chat_completion(self, *, model, messages, tools, max_tokens):
        _ = (model, messages, tools, max_tokens)
        self.calls += 1
        if self._error is not None:
            raise self._error
        if self._responses:
            return self._responses.pop(0)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='ok', tool_calls=[]))]
        )


def test_agent_policy_short_circuits_emergency_without_provider_call():
    gateway = _FakeGateway(error=RuntimeError('should not be called'))
    agent = OpenRouterAgent(api_key='explicit-key', gateway=gateway)

    result = asyncio.run(agent.generate_response('I have severe chest pain and difficulty breathing'))

    assert result == '<EMERGENCY_OVERRIDE>'
    assert gateway.calls == 0


def test_resilient_gateway_falls_back_to_secondary_gateway():
    primary = _FakeGateway(error=RuntimeError('primary down'))
    secondary = _FakeGateway()
    gateway = ResilientGateway(gateways=[primary, secondary], max_retries=0)

    result = asyncio.run(
        gateway.create_chat_completion(
            model='openai/gpt-4o-mini',
            messages=[{'role': 'user', 'content': 'hello'}],
            tools=[],
            max_tokens=128,
        )
    )

    assert result.choices[0].message.content == 'ok'
    assert primary.calls == 1
    assert secondary.calls == 1


def test_circuit_breaker_opens_after_failure_threshold():
    breaker = GatewayCircuitBreaker(failure_threshold=2, recovery_timeout_seconds=60)

    breaker.record_failure()
    assert breaker.can_execute() is True

    breaker.record_failure()
    assert breaker.can_execute() is False


def test_agent_rejects_unauthenticated_protected_tool_call():
    first_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='',
                    tool_calls=[
                        SimpleNamespace(
                            id='tool-1',
                            function=SimpleNamespace(
                                name='book_appointment',
                                arguments=json.dumps(
                                    {
                                        'time_slot': '2026-05-12T10:00:00',
                                        'symptoms_summary': 'Sore throat',
                                        'appointment_reason': 'Needs review',
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
        choices=[SimpleNamespace(message=SimpleNamespace(content='Cannot proceed.'))]
    )
    gateway = _FakeGateway(responses=[first_response, second_response])
    agent = OpenRouterAgent(api_key='explicit-key', gateway=gateway)

    result = asyncio.run(agent.generate_response('Book me a visit for tomorrow at 10'))

    assert result == 'Cannot proceed.'
    assert gateway.calls == 2
