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

    async def create_streaming_chat_completion(self, *, model, messages, tools, max_tokens):
        completion = await self.create_chat_completion(
            model=model,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
        )
        message = completion.choices[0].message
        tool_calls = getattr(message, 'tool_calls', None) or []
        if tool_calls:
            for index, tool_call in enumerate(tool_calls):
                yield SimpleNamespace(
                    choices=[SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[SimpleNamespace(
                                index=index,
                                id=getattr(tool_call, 'id', f'tool-{index}'),
                                function=SimpleNamespace(
                                    name=tool_call.function.name,
                                    arguments='',
                                ),
                            )],
                        ),
                        finish_reason=None,
                    )],
                )
                yield SimpleNamespace(
                    choices=[SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[SimpleNamespace(
                                index=index,
                                id=None,
                                function=SimpleNamespace(
                                    name=None,
                                    arguments=tool_call.function.arguments,
                                ),
                            )],
                        ),
                        finish_reason=None,
                    )],
                )
        else:
            yield SimpleNamespace(
                choices=[SimpleNamespace(
                    delta=SimpleNamespace(content=message.content, tool_calls=None),
                    finish_reason=None,
                )],
            )

        yield SimpleNamespace(
            choices=[SimpleNamespace(
                delta=SimpleNamespace(content=None, tool_calls=None),
                finish_reason='stop',
            )],
        )


def _collect_text_response(agent: OpenRouterAgent, prompt: str) -> str:
    async def _collect() -> str:
        chunks = [chunk async for chunk in agent.stream_response(prompt)]
        text_chunks: list[str] = []
        for chunk in chunks:
            if chunk.startswith('0:'):
                text_chunks.append(json.loads(chunk[2:]))
        return ''.join(text_chunks)

    return asyncio.run(_collect())


def test_agent_policy_short_circuits_emergency_without_provider_call():
    gateway = _FakeGateway(error=RuntimeError('should not be called'))
    agent = OpenRouterAgent(api_key='explicit-key', gateway=gateway)

    result = _collect_text_response(agent, 'I have severe chest pain and difficulty breathing')

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

    result = _collect_text_response(agent, 'Book me a visit for tomorrow at 10')

    assert result == 'Cannot proceed.'
    assert gateway.calls == 2
