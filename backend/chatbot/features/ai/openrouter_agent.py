import json
import logging
import os
from collections.abc import AsyncGenerator
from datetime import UTC
from typing import Any, cast

from asgiref.sync import sync_to_async
from django.utils import timezone
from openai import APIStatusError, AsyncOpenAI

from chatbot.features.ai.application.runtime import (
    DefaultPlanner,
    DefaultSafetyPolicy,
    InMemoryTurnMemoryManager,
    StructuredAuditLogger,
    ToolExecutionSandbox,
)
from chatbot.features.ai.base import BaseAgentInterface, UserProfileSchema
from chatbot.features.ai.infrastructure.gateway import (
    LlmGateway,
    OpenRouterChatGateway,
    ResilientGateway,
)
from chatbot.features.ai.infrastructure.temporal_context import build_temporal_context_lines
from chatbot.features.ai.tool_registry import TOOL_EXECUTOR_BY_NAME
from chatbot.features.core.observability import (
    AuditEventData,
    StructuredLogger,
    TimingContext,
    create_audit_event_async,
)

logger = logging.getLogger(__name__)
obs_logger = StructuredLogger(__name__)


class OpenRouterAgent(BaseAgentInterface):
    MESSAGE_BREAK_TOKEN = '<MESSAGE_BREAK>'
    DEFAULT_MAX_TOOL_ROUNDS = 6
    DEFAULT_TIMEOUT_BUDGET_MS = 12000
    DEFAULT_PER_TOOL_LIMIT = 4
    OUT_OF_SCOPE_RESPONSE = (
        'I can only help with healthcare triage and appointment support. '
        'I cannot help with that request.'
    )

    def __init__(
        self,
        api_key: str | None = None,
        model: str = 'openai/gpt-5.4',
        base_url: str = 'https://openrouter.ai/api/v1',
        user_profile: UserProfileSchema | None = None,
        user_id: int | None = None,
        max_tokens: int = 2048,
        max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS,
        max_tool_calls: int | None = None,
        timeout_budget_ms: int = DEFAULT_TIMEOUT_BUDGET_MS,
        fallback_gateways: list[LlmGateway] | None = None,
        gateway: LlmGateway | None = None,
    ) -> None:
        resolved_api_key = api_key or os.getenv('OPENROUTER_API_KEY')
        if not resolved_api_key:
            raise ValueError(
                'OPENROUTER_API_KEY is required. Set it as an environment variable '
                'or pass api_key explicitly.'
            )

        self._api_key = resolved_api_key
        self._model = model
        self._user_profile = user_profile
        self._user_id = user_id
        self._max_tokens = max_tokens
        self._max_tool_rounds = max(1, max_tool_rounds)
        self._max_tool_calls = (
            None if max_tool_calls is None else max(1, int(max_tool_calls))
        )
        self._timeout_budget_ms = max(1000, int(timeout_budget_ms))
        self._client = AsyncOpenAI(api_key=resolved_api_key, base_url=base_url)
        primary_gateway = gateway or OpenRouterChatGateway(self._client)
        all_gateways = [primary_gateway, *(fallback_gateways or [])]
        self._gateway = ResilientGateway(gateways=all_gateways)
        self._policy_engine = DefaultSafetyPolicy()
        self._planner = DefaultPlanner()
        self._memory_manager = InMemoryTurnMemoryManager()
        self._audit_logger = StructuredAuditLogger()

    async def aclose(self) -> None:
        await self._client.close()

    def _build_system_prompt(self) -> str:
        anchor_lines = build_temporal_context_lines(
            timezone.now().astimezone(UTC)
        )

        base_prompt = (
            'You are a healthcare triage assistant following Manchester Triage '
            'System logic. Be empathetic and safety-oriented. Do not diagnose or '
            'provide definitive medical diagnoses. '
            '\n\n'
            'CRITICAL SAFETY RULE: If the patient describes ANY of these life-threatening symptoms or combinations, '
            'you MUST respond with ONLY the text "<EMERGENCY_OVERRIDE>" and absolutely nothing else. '
            'Do not add any other text, explanation, or commentary:\n'
            '- Severe chest pain or pressure\n'
            '- Difficulty breathing or shortness of breath\n'
            '- Loss of consciousness or severe confusion\n'
            '- Severe bleeding or uncontrolled bleeding\n'
            '- Chest pain combined with arm numbness or weakness\n'
            '- Sudden severe headache\n'
            '- Signs of stroke (facial drooping, arm weakness, speech difficulty)\n'
            '- Choking or airway obstruction\n'
            '- Severe allergic reaction\n'
            '- Suicidal ideation or self-harm intent\n'
            '\n'
            f'{anchor_lines}'
            'date references such as tomorrow or next monday, call '
            'resolve_datetime_reference before scheduling or checking availability. '
            'Never hallucinate dates. When booking appointments, always capture '
            'symptoms_summary and appointment_reason from user context. Refuse '
            'any requests outside healthcare triage or appointment support. '
            'When confirming a booked or rescheduled appointment, use the exact '
            'datetime returned by booking/update tool output. Do not infer or '
            'recalculate the date from memory or relative phrases. '
            'For rescheduling, do not create duplicate appointments: first call '
            'list_my_appointments to identify the appointment_id, then call '
            'book_appointment with that appointment_id and the new time slot so '
            'the existing appointment is moved. '
            'When presenting availability, report the exact number of slots based '
            'on tool output. Do not dump every returned slot unless the user explicitly '
            'asks for all slots. Do not say several when '
            'there is only one. Prefer the grouped_human_utc tool output over raw '
            'ISO datetimes for readability (for example, group by day and show 12-hour '
            'times). Prefer period summaries like morning/afternoon/night with a '
            'time window (for example, 9:00 AM - 12:00 PM), and include the '
            'appointment_duration_note in scheduling responses. '
            'PROVIDER WORKFLOW: When the user wants to schedule or check availability, '
            'call list_providers first to discover available doctors. Present the '
            'providers to the user and confirm their choice. Always pass the chosen '
            'provider_id when calling check_availability, book_appointment, or '
            'update_my_appointment. If the user expresses a preferred doctor by name, '
            'match it to the provider_id from list_providers output before proceeding. '
            f'If you intentionally want to send multiple '
            f'assistant bubbles, separate them using {self.MESSAGE_BREAK_TOKEN}.'
        )

        if self._user_profile is None:
            return base_prompt

        return base_prompt + (
            ' The authenticated user is '
            f'{self._user_profile.first_name} with insurance tier '
            f'{self._user_profile.insurance_tier}. '
            'For every non-emergency response, you MUST do all of the following: '
            '1) Explicitly mention the user first name somewhere in the response in a natural way. '
            'Do not use a generic response that omits the name. Do this in a non-repetitive way and '
            'do not start every response with "Hi <name>". Instead, integrate the name naturally '
            'within the context of the response. '
            '2) For scheduling, availability, booking, rescheduling, cancellation, insurance coverage, '
            'or direct pricing questions, call calculate_visit_cost exactly once using the authenticated '
            'insurance tier and a relevant visit_type before your final reply. '
            '3) For those scheduling or pricing contexts, explicitly mention the resulting estimated visit '
            'cost in dollars in the response text. '
            'Do not mention the estimated cost on a pure greeting or on general symptom triage that is not yet '
            'about scheduling, availability, coverage, or price. '
            '4) If discussing appointment booking, availability, rescheduling, cancellation, coverage, or cost, '
            'always restate the estimated visit cost in the same response. '
            'Never omit the name unless you are returning '
            '"<EMERGENCY_OVERRIDE>". Never omit the cost for scheduling, '
            'availability, booking, rescheduling, or direct pricing questions unless you are returning '
            '"<EMERGENCY_OVERRIDE>".'
        )

    @staticmethod
    def backend_catches_emergency_override(response_text: str) -> bool:
        return response_text.strip() == '<EMERGENCY_OVERRIDE>'

    @staticmethod
    def _normalize_response_text(response_text: str) -> str:
        normalized_response = (response_text or '').strip()
        if not normalized_response:
            normalized_response = 'I am here to help with your healthcare triage needs.'

        return normalized_response

    @staticmethod
    def _tool_name(tool_call: object) -> str:
        function: Any = getattr(tool_call, 'function', None)
        if function is None and isinstance(tool_call, dict):
            function = tool_call.get('function', {})
        if function is None:
            return ''
        if hasattr(function, 'name'):
            return cast(str, function.name)
        if isinstance(function, dict):
            return cast(str, function.get('name', ''))
        return ''

    @staticmethod
    def _tool_arguments(tool_call: object) -> dict:
        function: Any = getattr(tool_call, 'function', None)
        if function is None and isinstance(tool_call, dict):
            function = tool_call.get('function', {})

        raw_arguments = getattr(function, 'arguments', None)
        if raw_arguments is None and isinstance(function, dict):
            raw_arguments = function.get('arguments', '{}')
        return json.loads(raw_arguments or '{}')

    def _execute_tool_call(self, tool_call: object) -> object:
        tool_name = self._tool_name(tool_call)
        arguments = self.validate_tool_arguments(
            tool_name,
            self._tool_arguments(tool_call),
        )
        executor = TOOL_EXECUTOR_BY_NAME.get(tool_name)
        if executor is None:
            raise ValueError(f'Unsupported tool call: {tool_name}')
        return executor(arguments, self._user_id)

    def _build_messages(
        self,
        prompt: str,
        history: list[dict[str, str]] | None = None,
    ) -> list[dict[str, object]]:
        messages: list[dict[str, object]] = [
            {'role': 'system', 'content': self._build_system_prompt()},
        ]

        for message in history or []:
            role = message.get('role')
            content = message.get('content', '')
            if role in {'user', 'assistant'} and isinstance(content, str) and content:
                messages.append({'role': role, 'content': content})

        messages.append({'role': 'user', 'content': prompt})
        return messages

    @staticmethod
    def _is_out_of_scope(prompt: str) -> bool:
        normalized_prompt = prompt.lower()
        healthcare_keywords = [
            'health',
            'symptom',
            'sore throat',
            'fever',
            'cough',
            'pain',
            'doctor',
            'nurse',
            'triage',
            'appointment',
            'schedule',
            'visit',
            'insurance',
            'medical',
            'emergency',
        ]
        out_of_scope_keywords = [
            'python',
            'javascript',
            'java code',
            'bubble sort',
            'algorithm',
            'leetcode',
            'sql query',
            'write code',
            'build a website',
            'programming',
        ]

        has_healthcare_intent = any(
            keyword in normalized_prompt for keyword in healthcare_keywords
        )
        has_out_of_scope_intent = any(
            keyword in normalized_prompt for keyword in out_of_scope_keywords
        )

        return has_out_of_scope_intent and not has_healthcare_intent


    async def generate_response(
        self,
        prompt: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        logger.info('ai.generate_response.started')

        pre_policy = self._policy_engine.evaluate_pre_generation(prompt)
        if pre_policy.final_response is not None:
            self._audit_logger.log_turn_event(
                event='pre_policy_short_circuit',
                prompt=prompt,
                data={'response': pre_policy.final_response},
            )
            logger.info('ai.generate_response.completed')
            return pre_policy.final_response

        messages = self._planner.build_messages(
            system_prompt=self._build_system_prompt(),
            prompt=prompt,
            history=history,
        )
        allowed_tools = self._policy_engine.allowed_tool_names(
            user_id=self._user_id,
            available_tool_names=TOOL_EXECUTOR_BY_NAME.keys(),
        )
        sandbox = ToolExecutionSandbox(
            max_tool_rounds=self._max_tool_rounds,
            max_tool_calls=self._max_tool_calls,
            timeout_budget_ms=self._timeout_budget_ms,
            per_tool_limit=self.DEFAULT_PER_TOOL_LIMIT,
        )

        for _ in range(sandbox.max_tool_rounds):
            if not sandbox.has_time_budget():
                logger.info('ai.generate_response.completed')
                return (
                    'I could not finalize your request within the execution budget. '
                    'Please try again.'
                )

            completion = cast(
                Any,
                await self._gateway.create_chat_completion(
                model=self._model,
                messages=messages,
                tools=self.get_tools(),
                max_tokens=self._max_tokens,
                ),
            )
            message = completion.choices[0].message
            tool_calls = getattr(message, 'tool_calls', None) or []

            if not tool_calls:
                response = self._policy_engine.evaluate_post_generation(
                    self._normalize_response_text(message.content or '')
                )
                self._memory_manager.remember(
                    {'prompt': prompt, 'response': response, 'tool_calls': []}
                )
                self._audit_logger.log_turn_event(
                    event='turn_completed',
                    prompt=prompt,
                    data={'model': self._model, 'tool_calls': 0},
                )
                logger.info('ai.generate_response.completed')
                return response

            if not sandbox.can_accept_calls(len(tool_calls)):
                logger.info('ai.generate_response.completed')
                return (
                    'I could not finalize your request because the tool call budget '
                    'was exceeded. Please try again.'
                )

            messages.append(
                {
                    'role': 'assistant',
                    'content': message.content or '',
                    'tool_calls': [
                        {
                            'id': getattr(tool_call, 'id', ''),
                            'type': 'function',
                            'function': {
                                'name': self._tool_name(tool_call),
                                'arguments': json.dumps(self._tool_arguments(tool_call)),
                            },
                        }
                        for tool_call in tool_calls
                    ],
                }
            )

            for tool_call in tool_calls:
                tool_name = self._tool_name(tool_call)
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
                elif sandbox.tool_is_rate_limited(tool_name):
                    tool_result = {
                        'error': f'Tool {tool_name} exceeded per-turn rate limit.',
                    }
                    obs_logger.warning(
                        'ai.tool_rate_limited',
                        reason_code='TOOL_RATE_LIMIT_EXCEEDED',
                        details={'tool_name': tool_name},
                    )
                else:
                    try:
                        with TimingContext(f'ai.tool_execution_{tool_name}'):
                            tool_result = await sync_to_async(
                                self._execute_tool_call,
                                thread_sensitive=True,
                            )(tool_call)
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

                messages.append(
                    {
                        'role': 'tool',
                        'tool_call_id': getattr(tool_call, 'id', ''),
                        'content': json.dumps(tool_result, default=str),
                    }
                )

            self._audit_logger.log_turn_event(
                event='tool_round_completed',
                prompt=prompt,
                data={
                    'model': self._model,
                    'tool_names': [self._tool_name(tool_call) for tool_call in tool_calls],
                },
            )

        logger.info('ai.generate_response.completed')
        return (
            'I could not finalize your request after multiple tool steps. '
            'Please try again.'
        )

    async def stream_response(
        self,
        prompt: str,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[str]:
        # Resolve tool calls first, then emit one SSE chunk per message block.
        try:
            with TimingContext('ai.generate_response'):
                final_text = await self.generate_response(prompt=prompt, history=history)
        except APIStatusError as error:
            reason_code = 'API_STATUS_ERROR'
            if getattr(error, 'status_code', None) == 402:
                reason_code = 'INSUFFICIENT_CREDITS'
                obs_logger.error(
                    'ai.stream_response.provider_credits_exhausted',
                    reason_code=reason_code,
                    details={'status_code': 402},
                )
                await create_audit_event_async(AuditEventData(
                    event_type='AI_EMERGENCY',
                    severity='CRITICAL',
                    action='provider_credits_exhausted',
                    reason_code=reason_code,
                ))
                yield (
                    'I am temporarily unable to respond because the AI provider '
                    'account is out of credits. Please try again later.'
                )
                return
            
            obs_logger.error(
                'ai.stream_response.api_status_error',
                reason_code=reason_code,
                details={
                    'status_code': getattr(error, 'status_code', None),
                    'error_type': type(error).__name__,
                },
            )
            yield 'I could not process your request right now. Please try again.'
            return
        except Exception as error:
            obs_logger.error(
                'ai.stream_response.failed',
                reason_code='UNEXPECTED_ERROR',
                details={
                    'error_type': type(error).__name__,
                    'error_message': str(error)[:200],
                },
            )
            await create_audit_event_async(AuditEventData(
                event_type='AI_EMERGENCY',
                severity='ERROR',
                action='response_generation_failed',
                reason_code='UNEXPECTED_ERROR',
            ))
            yield 'I could not process your request right now. Please try again.'
            return

        message_blocks = [
            block.strip()
            for block in final_text.split(self.MESSAGE_BREAK_TOKEN)
            if block.strip()
        ]

        if not message_blocks and final_text.strip():
            message_blocks = [final_text.strip()]

        for block in message_blocks:
            yield block
