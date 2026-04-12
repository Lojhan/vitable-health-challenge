from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from asgiref.sync import sync_to_async

from chatbot.features.ai.application.runtime import ToolExecutionSandbox
from chatbot.features.core.observability import (
    AuditEventData,
    StructuredLogger,
    TimingContext,
    create_audit_event_async,
)

obs_logger = StructuredLogger(__name__)

ToolArgumentValidator = Callable[[str, dict[str, object]], dict[str, object]]
ToolExecutorRegistry = Mapping[str, Callable[[dict[str, object], int | None], object]]


@dataclass(frozen=True)
class ParsedToolCall:
    tool_name: str
    arguments: dict[str, object]
    tool_call_id: str = ''

    def as_assistant_tool_call(self) -> dict[str, object]:
        return {
            'id': self.tool_call_id,
            'type': 'function',
            'function': {
                'name': self.tool_name,
                'arguments': json.dumps(self.arguments),
            },
        }


@dataclass(frozen=True)
class ToolExecutionResult:
    parsed_call: ParsedToolCall
    payload: object


class ToolCallParser:
    @staticmethod
    def parse_streamed(tool_calls_by_index: dict[int, dict[str, str]]) -> list[ParsedToolCall]:
        return [
            ParsedToolCall(
                tool_name=tool_call['name'],
                arguments=json.loads(tool_call['arguments'] or '{}'),
                tool_call_id=tool_call['id'],
            )
            for _, tool_call in sorted(tool_calls_by_index.items())
        ]


class ToolExecutor:
    def __init__(
        self,
        *,
        validator: ToolArgumentValidator,
        executor_registry: ToolExecutorRegistry,
        user_id: int | None,
    ) -> None:
        self._validator = validator
        self._executor_registry = executor_registry
        self._user_id = user_id

    async def execute(
        self,
        parsed_call: ParsedToolCall,
        *,
        allowed_tools: set[str],
        sandbox: ToolExecutionSandbox,
    ) -> ToolExecutionResult:
        tool_name = parsed_call.tool_name
        tool_result: object = {
            'error': f'Tool {tool_name} failed unexpectedly.',
            'tool_name': tool_name,
        }

        sandbox.register_call(tool_name)
        if tool_name not in allowed_tools:
            tool_result = {
                'error': f'Tool {tool_name} is not allowed for this request context.',
            }
            obs_logger.warning(
                'ai.tool_not_allowed',
                reason_code='TOOL_NOT_ALLOWED',
                details={'tool_name': tool_name},
            )
            return ToolExecutionResult(parsed_call=parsed_call, payload=tool_result)

        if sandbox.tool_is_rate_limited(tool_name):
            tool_result = {
                'error': f'Tool {tool_name} exceeded per-turn rate limit.',
            }
            obs_logger.warning(
                'ai.tool_rate_limited',
                reason_code='TOOL_RATE_LIMIT_EXCEEDED',
                details={'tool_name': tool_name},
            )
            return ToolExecutionResult(parsed_call=parsed_call, payload=tool_result)

        try:
            validated_args = self._validator(tool_name, parsed_call.arguments)
            executor = self._executor_registry.get(tool_name)
            if executor is None:
                raise ValueError(f'Unsupported tool call: {tool_name}')
            with TimingContext(f'ai.tool_execution_{tool_name}'):
                tool_result = await sync_to_async(
                    executor,
                    thread_sensitive=True,
                )(validated_args, self._user_id)
            json.dumps(tool_result, default=str)
        except Exception as error:
            tool_result = {
                'error': str(error),
                'tool_name': tool_name,
            }
            obs_logger.error(
                'ai.tool_execution_failed',
                reason_code='TOOL_EXECUTION_ERROR',
                details={
                    'tool_name': tool_name,
                    'error_type': type(error).__name__,
                    'error_message': str(error)[:200],
                },
            )
            await create_audit_event_async(AuditEventData(
                event_type='TOOL_FAILURE',
                severity='ERROR',
                resource_type='tool',
                resource_id=tool_name,
                action='execution_failed',
                reason_code='TOOL_EXECUTION_ERROR',
            ))

        return ToolExecutionResult(parsed_call=parsed_call, payload=tool_result)


def build_assistant_tool_calls(parsed_calls: Sequence[ParsedToolCall]) -> list[dict[str, object]]:
    return [parsed_call.as_assistant_tool_call() for parsed_call in parsed_calls]


def build_tool_message(tool_call_id: str, payload: object) -> dict[str, object]:
    return {
        'role': 'tool',
        'tool_call_id': tool_call_id,
        'content': json.dumps(payload, default=str),
    }


def normalize_response_text(response_text: str) -> str:
    normalized_response = (response_text or '').strip()
    if not normalized_response:
        return 'I am here to help with your healthcare triage needs.'
    return normalized_response
