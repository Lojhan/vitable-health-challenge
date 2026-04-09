import os
import json
from collections.abc import AsyncGenerator
from datetime import datetime
from datetime import timedelta
from datetime import timezone as dt_timezone
from typing import Any, cast

from openai import AsyncOpenAI
from openai import APIStatusError
from django.utils import timezone

from chatbot.features.ai.base import BaseAgentInterface, UserProfileSchema
from chatbot.features.billing.pricing import calculate_visit_cost
from chatbot.features.scheduling.tools import (
    book_appointment,
    cancel_user_appointment,
    check_availability,
    list_providers,
    list_user_appointments,
    resolve_datetime_reference,
    update_user_appointment,
)


class OpenRouterAgent(BaseAgentInterface):
    MESSAGE_BREAK_TOKEN = '<MESSAGE_BREAK>'
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
        self._client = AsyncOpenAI(api_key=resolved_api_key, base_url=base_url)

    async def aclose(self) -> None:
        await self._client.close()

    def _build_system_prompt(self) -> str:
        now_utc = timezone.now().astimezone(dt_timezone.utc)
        anchor_today = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        anchor_tomorrow = anchor_today + timedelta(days=1)
        anchor_day_after_tomorrow = anchor_today + timedelta(days=2)
        anchor_next_week = anchor_today + timedelta(days=7)
        anchor_in_two_weeks = anchor_today + timedelta(days=14)
        anchor_other_week = anchor_today - timedelta(days=7)
        anchor_in_a_month = anchor_today + timedelta(days=30)

        anchor_lines = (
            'TEMPORAL ANCHORS (pre-calculated UTC datetimes, use these exact anchors before tool calls):\n'
            f'- today: {anchor_today.isoformat()}\n'
            f'- tomorrow: {anchor_tomorrow.isoformat()}\n'
            f'- the day after tomorrow: {anchor_day_after_tomorrow.isoformat()}\n'
            f'- next week: {anchor_next_week.isoformat()}\n'
            f'- in two weeks: {anchor_in_two_weeks.isoformat()}\n'
            f'- the other week (past context only): {anchor_other_week.isoformat()}\n'
            f'- in a month: {anchor_in_a_month.isoformat()}\n'
            'Combine anchor date with explicit user-provided time when available.\n\n'
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

    @staticmethod
    def _format_availability_payload(slots: list[str]) -> dict[str, object]:
        def period_for_hour(hour: int) -> str:
            if 5 <= hour <= 12:
                return 'morning'
            if 13 <= hour <= 17:
                return 'afternoon'
            return 'night'

        def format_hour_label(hour: int) -> str:
            label = datetime(2026, 1, 1, hour, 0, 0).strftime('%I:%M %p')
            return label.lstrip('0')

        parsed_slots: list[datetime] = [datetime.fromisoformat(slot) for slot in slots]
        grouped: dict[tuple[str, str, str], list[int]] = {}

        for parsed in parsed_slots:
            day_label = parsed.strftime('%A, %B %d')
            day_iso = parsed.strftime('%Y-%m-%d')
            period = period_for_hour(parsed.hour)
            grouped.setdefault((day_iso, day_label, period), []).append(parsed.hour)

        grouped_human_utc: list[dict[str, object]] = []
        for (day_iso, day_label, period), hours in grouped.items():
            sorted_hours = sorted(set(hours))
            ranges: list[str] = []
            if sorted_hours:
                range_start = sorted_hours[0]
                range_end = sorted_hours[0]
                for hour in sorted_hours[1:]:
                    if hour == range_end + 1:
                        range_end = hour
                    else:
                        ranges.append(
                            f'{format_hour_label(range_start)} - {format_hour_label(range_end + 1)}'
                        )
                        range_start = hour
                        range_end = hour

                ranges.append(
                    f'{format_hour_label(range_start)} - {format_hour_label(range_end + 1)}'
                )

            grouped_human_utc.append(
                {
                    'day_iso_utc': day_iso,
                    'day': day_label,
                    'period': period,
                    'windows_utc': ranges,
                    'slot_count': len(sorted_hours),
                }
            )

        period_order = {'morning': 0, 'afternoon': 1, 'night': 2}
        grouped_human_utc.sort(
            key=lambda item: (
                cast(str, item['day_iso_utc']),
                period_order.get(cast(str, item['period']), 99),
            )
        )

        summary_lines = [
            (
                f"{item['day']} ({cast(str, item['period']).capitalize()}): "
                f"{', '.join(cast(list[str], item['windows_utc']))}"
            )
            for item in grouped_human_utc
        ]

        return {
            'total_slots': len(slots),
            'grouped_human_utc': grouped_human_utc,
            'summary_lines': summary_lines,
            'timezone': 'UTC',
            'appointment_duration_note': '*Appointments last 1h.',
        }

    def _execute_tool_call(self, tool_call: object) -> object:
        tool_name = self._tool_name(tool_call)
        arguments = self._tool_arguments(tool_call)

        if tool_name == 'calculate_visit_cost':
            return calculate_visit_cost(
                insurance_tier=arguments['insurance_tier'],
                visit_type=arguments['visit_type'],
            )
        if tool_name == 'resolve_datetime_reference':
            return resolve_datetime_reference(
                datetime_reference=arguments['datetime_reference']
            )
        if tool_name == 'check_availability':
            slots = check_availability(
                date_range_str=arguments['date_range_str'],
                provider_id=arguments.get('provider_id'),
            )
            return self._format_availability_payload(slots)
        if tool_name == 'list_providers':
            return list_providers()
        if tool_name == 'book_appointment':
            if self._user_id is None:
                raise ValueError('Authenticated user_id is required for appointment tools')
            appointment = book_appointment(
                user_id=self._user_id,
                appointment_id=arguments.get('appointment_id'),
                time_slot=arguments['time_slot'],
                rrule_str=arguments.get('rrule_str'),
                symptoms_summary=arguments['symptoms_summary'],
                appointment_reason=arguments['appointment_reason'],
                provider_id=arguments.get('provider_id'),
            )
            appointment_provider_id = cast(Any, appointment).provider_id
            return {
                'appointment_id': int(appointment.pk),
                'provider_id': int(appointment_provider_id)
                if appointment_provider_id is not None
                else None,
                'time_slot_utc': appointment.time_slot.astimezone(dt_timezone.utc).replace(
                    microsecond=0
                ).isoformat(),
                'time_slot_human_utc': appointment.time_slot.astimezone(
                    dt_timezone.utc
                ).strftime('%A, %B %d, %Y at %I:%M %p UTC'),
            }

        if tool_name == 'list_my_appointments':
            if self._user_id is None:
                raise ValueError('Authenticated user_id is required for appointment tools')
            return list_user_appointments(user_id=self._user_id)

        if tool_name == 'cancel_my_appointment':
            if self._user_id is None:
                raise ValueError('Authenticated user_id is required for appointment tools')
            return cancel_user_appointment(
                user_id=self._user_id,
                appointment_id=arguments['appointment_id'],
            )

        if tool_name == 'update_my_appointment':
            if self._user_id is None:
                raise ValueError('Authenticated user_id is required for appointment tools')
            return update_user_appointment(
                user_id=self._user_id,
                appointment_id=arguments['appointment_id'],
                time_slot=arguments.get('time_slot'),
                rrule_str=arguments.get('rrule_str'),
                symptoms_summary=arguments.get('symptoms_summary'),
                appointment_reason=arguments.get('appointment_reason'),
                provider_id=arguments.get('provider_id'),
            )

        raise ValueError(f'Unsupported tool call: {tool_name}')

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
        if self._is_out_of_scope(prompt):
            return self.OUT_OF_SCOPE_RESPONSE

        messages = self._build_messages(prompt=prompt, history=history)
        max_tool_rounds = 6

        for _ in range(max_tool_rounds):
            completion = await self._client.chat.completions.create(
                model=self._model,
                messages=cast(Any, messages),
                tools=cast(Any, self.get_tools()),
                max_tokens=self._max_tokens,
            )
            message = completion.choices[0].message
            tool_calls = getattr(message, 'tool_calls', None) or []

            if not tool_calls:
                return self._normalize_response_text(message.content or '')

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
                previous_async_unsafe = os.environ.get('DJANGO_ALLOW_ASYNC_UNSAFE')
                os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
                try:
                    tool_result = self._execute_tool_call(tool_call)
                finally:
                    if previous_async_unsafe is None:
                        del os.environ['DJANGO_ALLOW_ASYNC_UNSAFE']
                    else:
                        os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = previous_async_unsafe

                messages.append(
                    {
                        'role': 'tool',
                        'tool_call_id': getattr(tool_call, 'id', ''),
                        'content': json.dumps(tool_result, default=str),
                    }
                )

        return (
            'I could not finalize your request after multiple tool steps. '
            'Please try again.'
        )

    async def stream_response(
        self,
        prompt: str,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[str, None]:
        # Resolve tool calls first, then emit one SSE chunk per message block.
        try:
            final_text = await self.generate_response(prompt=prompt, history=history)
        except APIStatusError as error:
            print(f'APIStatusError during response generation: {error}')
            if getattr(error, 'status_code', None) == 402:
                yield (
                    'I am temporarily unable to respond because the AI provider '
                    'account is out of credits. Please try again later.'
                )
                return
            yield 'I could not process your request right now. Please try again.'
            return
        except Exception:
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
