import logging
import os
from collections.abc import AsyncGenerator
from datetime import UTC
from typing import Any, cast

from django.utils import timezone
from openai import APIStatusError, AsyncOpenAI

from chatbot.features.ai.application.runtime import (
    DefaultPlanner,
    DefaultSafetyPolicy,
    InMemoryTurnMemoryManager,
    StructuredAuditLogger,
    ToolExecutionSandbox,
)
from chatbot.features.ai.application.tool_runtime import (
    ParsedToolCall,
    ToolCallParser,
    ToolExecutor,
    build_assistant_tool_calls,
    build_tool_message,
    normalize_response_text,
)
from chatbot.features.ai.base import BaseAgentInterface, UserProfileSchema
from chatbot.features.ai.infrastructure.gateway import (
    LlmGateway,
    OpenRouterChatGateway,
    ResilientGateway,
)
from chatbot.features.ai.infrastructure.temporal_context import build_temporal_context_lines
from chatbot.features.ai.tool_registry import TOOL_EXECUTOR_BY_NAME
from chatbot.features.ai.ui_tool_registry import (
    build_visible_tool_payload,
    get_tool_activity_label,
    get_ui_kind,
)
from chatbot.features.chat.stream_protocol import (
    encode_error,
    encode_finish,
    encode_status,
    encode_text_delta,
    encode_tool_call,
    encode_tool_result,
)
from chatbot.features.core.observability import (
    AuditEventData,
    StructuredLogger,
    create_audit_event_async,
)

logger = logging.getLogger(__name__)
obs_logger = StructuredLogger(__name__)


class OpenRouterAgent(BaseAgentInterface):
    DEFAULT_MAX_TOOL_ROUNDS = 6
    DEFAULT_TIMEOUT_BUDGET_MS = 12000
    DEFAULT_PER_TOOL_LIMIT = 4
    EXECUTION_BUDGET_EXCEEDED_RESPONSE = (
        'I could not finalize your request within the execution budget. '
        'Please try again.'
    )
    TOOL_BUDGET_EXCEEDED_RESPONSE = (
        'I could not finalize your request because the tool call budget '
        'was exceeded. Please try again.'
    )
    MAX_TOOL_ROUNDS_EXCEEDED_RESPONSE = (
        'I could not finalize your request after multiple tool steps. '
        'Please try again.'
    )
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
            'there is only one. The availability tool returns raw scheduling data '
            '(for example RRULE availability, blocked slots, and the requested UTC '
            'window) that the frontend renders for the user. Do not restate that raw '
            'data as JSON, and include the appointment_duration_note in scheduling '
            'responses when relevant. When you intentionally return structured '
            'availability JSON yourself, use type availability for broad calendar '
            'selection, availability_day for a specific date, and '
            'availability_slots for a narrowed subset such as morning or afternoon, '
            'while keeping the same raw scheduling fields. '
            'AUTO-RENDERED TOOL RESULTS: When you call show_providers_for_selection, '
            'check_availability, or list_my_appointments, the results are automatically displayed to the user as '
            'rich visual components (cards, tables, etc.). Do NOT repeat, re-list, dump as JSON, '
            'or narrate the returned data in your text response. Instead, provide only a brief '
            'contextual comment (e.g. "Here are some providers that match" or '
            '"I found available slots for next week"). The user can already see the full data '
            'in the rendered component.\n'
            'PROVIDER WORKFLOW: Use list_providers as a silent backend-only lookup to '
            'resolve provider_id values for scheduling steps, including matching a '
            'doctor name mentioned by the user. Use show_providers_for_selection only '
            'when the user explicitly asks to browse providers, compare options, or '
            'pick from a visible list. Always pass the chosen provider_id when calling '
            'check_availability, book_appointment, or update_my_appointment. If the '
            'user expresses a preferred doctor by name, match it to the provider_id '
            'from list_providers output before proceeding. If the silent list_providers '
            'JSON output is already in the conversation history, you do NOT need to '
            'call it again and can proceed directly.'
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

    def _build_sandbox(self) -> ToolExecutionSandbox:
        return ToolExecutionSandbox(
            max_tool_rounds=self._max_tool_rounds,
            max_tool_calls=self._max_tool_calls,
            timeout_budget_ms=self._timeout_budget_ms,
            per_tool_limit=self.DEFAULT_PER_TOOL_LIMIT,
        )

    def _get_allowed_tools(self) -> set[str]:
        return self._policy_engine.allowed_tool_names(
            user_id=self._user_id,
            available_tool_names=TOOL_EXECUTOR_BY_NAME.keys(),
        )

    def _build_tool_executor(self) -> ToolExecutor:
        return ToolExecutor(
            validator=self.validate_tool_arguments,
            executor_registry=TOOL_EXECUTOR_BY_NAME,
            user_id=self._user_id,
        )

    def _build_prompt_messages(
        self,
        prompt: str,
        history: list[dict[str, str]] | None,
    ) -> list[dict[str, object]]:
        return self._planner.build_messages(
            system_prompt=self._build_system_prompt(),
            prompt=prompt,
            history=history,
        )

    def _log_turn_completed(
        self,
        *,
        prompt: str,
        response: str,
    ) -> None:
        self._memory_manager.remember(
            {'prompt': prompt, 'response': response, 'tool_calls': []}
        )
        self._audit_logger.log_turn_event(
            event='turn_completed',
            prompt=prompt,
            data={'model': self._model, 'tool_calls': 0},
        )

    def _log_tool_round_completion(
        self,
        *,
        prompt: str,
        tool_names: list[str],
    ) -> None:
        self._audit_logger.log_turn_event(
            event='tool_round_completed',
            prompt=prompt,
            data={
                'model': self._model,
                'tool_names': tool_names,
            },
        )

    async def _execute_tool_round(
        self,
        *,
        parsed_tool_calls: tuple[ParsedToolCall, ...],
        messages: list[dict[str, object]],
        allowed_tools: set[str],
        sandbox: ToolExecutionSandbox,
        emit_status: bool = False,
    ) -> AsyncGenerator[tuple[str, object]]:
        tool_executor = self._build_tool_executor()

        for parsed_call in parsed_tool_calls:
            if emit_status:
                yield ('status', parsed_call)

            execution_result = await tool_executor.execute(
                parsed_call,
                allowed_tools=allowed_tools,
                sandbox=sandbox,
            )
            messages.append(
                build_tool_message(
                    execution_result.parsed_call.tool_call_id,
                    execution_result.payload,
                )
            )
            yield ('result', execution_result)


    async def stream_response(
        self,
        prompt: str,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[str]:
        """True token-streaming async generator using Data Stream Protocol.

        Yields protocol-encoded lines (``{prefix}:{payload}\\n``) that
        ``sse.py`` wraps in ``data:`` frames.
        """
        try:
            pre_policy = self._policy_engine.evaluate_pre_generation(prompt)
            if pre_policy.final_response is not None:
                yield encode_text_delta(pre_policy.final_response)
                yield encode_finish()
                return

            messages = self._build_prompt_messages(prompt, history)
            allowed_tools = self._get_allowed_tools()
            sandbox = self._build_sandbox()

            for _ in range(sandbox.max_tool_rounds):
                if not sandbox.has_time_budget():
                    yield encode_text_delta(self.EXECUTION_BUDGET_EXCEEDED_RESPONSE)
                    yield encode_finish('timeout')
                    return

                # -- Stream one completion round --
                text_content = ''
                tool_calls_by_index: dict[int, dict[str, str]] = {}
                finish_reason = 'stop'

                async for chunk in self._gateway.create_streaming_chat_completion(
                    model=self._model,
                    messages=messages,
                    tools=self.get_tools(),
                    max_tokens=self._max_tokens,
                ):
                    chunk = cast(Any, chunk)
                    if not chunk.choices:
                        continue

                    delta = chunk.choices[0].delta
                    choice_finish = chunk.choices[0].finish_reason

                    # Text delta — forward immediately
                    if delta.content:
                        text_content += delta.content
                        yield encode_text_delta(delta.content)

                    # Tool call delta — buffer arguments
                    if delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            idx = tc_delta.index
                            if idx not in tool_calls_by_index:
                                tool_calls_by_index[idx] = {
                                    'id': tc_delta.id or '',
                                    'name': '',
                                    'arguments': '',
                                }
                            entry = tool_calls_by_index[idx]
                            if tc_delta.id:
                                entry['id'] = tc_delta.id
                            if tc_delta.function:
                                if tc_delta.function.name:
                                    entry['name'] = tc_delta.function.name
                                if tc_delta.function.arguments:
                                    entry['arguments'] += tc_delta.function.arguments

                    if choice_finish:
                        finish_reason = choice_finish

                # -- No tool calls → done --
                if not tool_calls_by_index:
                    final_text = normalize_response_text(text_content)
                    if self.backend_catches_emergency_override(final_text):
                        yield encode_text_delta('<EMERGENCY_OVERRIDE>')
                    elif not text_content.strip():
                        # Nothing was streamed (empty response) — send normalized fallback
                        yield encode_text_delta(final_text)

                    self._log_turn_completed(prompt=prompt, response=text_content)
                    yield encode_finish(finish_reason)
                    return

                # -- Tool calls: execute each --
                if not sandbox.can_accept_calls(len(tool_calls_by_index)):
                    yield encode_text_delta(self.TOOL_BUDGET_EXCEEDED_RESPONSE)
                    yield encode_finish('tool_budget_exceeded')
                    return

                # Append assistant message with tool_calls to conversation
                parsed_tool_calls = tuple(
                    ToolCallParser.parse_streamed(tool_calls_by_index)
                )
                assistant_tool_calls = build_assistant_tool_calls(parsed_tool_calls)

                messages.append({
                    'role': 'assistant',
                    'content': text_content or '',
                    'tool_calls': assistant_tool_calls,
                })

                async for event_type, event_payload in self._execute_tool_round(
                    parsed_tool_calls=parsed_tool_calls,
                    messages=messages,
                    allowed_tools=allowed_tools,
                    sandbox=sandbox,
                    emit_status=True,
                ):
                    if event_type == 'status':
                        parsed_call = cast(ParsedToolCall, event_payload)
                        activity_label = get_tool_activity_label(parsed_call.tool_name)
                        ui_kind = get_ui_kind(parsed_call.tool_name)
                        yield encode_tool_call(
                            tool_call_id=parsed_call.tool_call_id,
                            tool_name=parsed_call.tool_name,
                            label=activity_label,
                            phase='started',
                        )
                        if ui_kind:
                            skeleton_payload = build_visible_tool_payload(
                                tool_name=parsed_call.tool_name,
                                tool_call_id=parsed_call.tool_call_id,
                                state='skeleton',
                            )
                            if skeleton_payload is not None:
                                yield encode_tool_result(
                                    tool_name=parsed_call.tool_name,
                                    tool_call_id=parsed_call.tool_call_id,
                                    ui_kind=ui_kind,
                                    result=skeleton_payload,
                                )
                        yield encode_status({
                            'tool_call_id': parsed_call.tool_call_id,
                            'tool_name': parsed_call.tool_name,
                            'label': activity_label,
                            'phase': 'running',
                            'state': 'active',
                        })
                        if ui_kind:
                            partial_payload = build_visible_tool_payload(
                                tool_name=parsed_call.tool_name,
                                tool_call_id=parsed_call.tool_call_id,
                                state='partial',
                            )
                            if partial_payload is not None:
                                yield encode_tool_result(
                                    tool_name=parsed_call.tool_name,
                                    tool_call_id=parsed_call.tool_call_id,
                                    ui_kind=ui_kind,
                                    result=partial_payload,
                                )
                        continue

                    execution_result = cast(Any, event_payload)
                    ui_kind = get_ui_kind(execution_result.parsed_call.tool_name)
                    if ui_kind:
                        has_error = (
                            isinstance(execution_result.payload, dict)
                            and 'error' in execution_result.payload
                        )
                        visible_payload = build_visible_tool_payload(
                            tool_name=execution_result.parsed_call.tool_name,
                            tool_call_id=execution_result.parsed_call.tool_call_id,
                            state='error' if has_error else 'final',
                            result=None if has_error else execution_result.payload,
                            error_message=(
                                str(execution_result.payload.get('error'))
                                if has_error else None
                            ),
                        )
                        if visible_payload is None:
                            continue
                        yield encode_tool_result(
                            tool_name=execution_result.parsed_call.tool_name,
                            tool_call_id=execution_result.parsed_call.tool_call_id,
                            ui_kind=ui_kind,
                            result=visible_payload,
                        )

                self._log_tool_round_completion(
                    prompt=prompt,
                    tool_names=[parsed_call.tool_name for parsed_call in parsed_tool_calls],
                )

            # Exhausted all tool rounds
            yield encode_text_delta(self.MAX_TOOL_ROUNDS_EXCEEDED_RESPONSE)
            yield encode_finish('max_rounds')

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
                yield encode_error(
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
            yield encode_error('I could not process your request right now. Please try again.')
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
            yield encode_error('I could not process your request right now. Please try again.')
