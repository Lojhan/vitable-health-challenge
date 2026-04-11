from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from time import monotonic
from typing import ClassVar

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PrePolicyDecision:
    final_response: str | None


class DefaultSafetyPolicy:
    OUT_OF_SCOPE_RESPONSE = (
        'I can only help with healthcare triage and appointment support. '
        'I cannot help with that request.'
    )
    _AUTHENTICATED_TOOLS: ClassVar[set[str]] = {
        'book_appointment',
        'list_my_appointments',
        'cancel_my_appointment',
        'update_my_appointment',
    }
    _EMERGENCY_HINT_GROUPS: ClassVar[list[tuple[str, ...]]] = [
        ('chest pain',),
        ('difficulty breathing',),
        ('shortness of breath',),
        ('loss of consciousness',),
        ('severe bleeding',),
        ('facial drooping', 'arm weakness', 'speech difficulty'),
        ('suicidal',),
    ]

    def evaluate_pre_generation(self, prompt: str) -> PrePolicyDecision:
        normalized = prompt.lower()
        if self._has_emergency_signal(normalized):
            return PrePolicyDecision(final_response='<EMERGENCY_OVERRIDE>')
        if self._is_out_of_scope(normalized):
            return PrePolicyDecision(final_response=self.OUT_OF_SCOPE_RESPONSE)
        return PrePolicyDecision(final_response=None)

    def allowed_tool_names(
        self,
        *,
        user_id: int | None,
        available_tool_names: Iterable[str],
    ) -> set[str]:
        allowed = set(available_tool_names)
        if user_id is None:
            allowed -= self._AUTHENTICATED_TOOLS
        return allowed

    def evaluate_post_generation(self, response_text: str) -> str:
        # Simple PHI guardrail: redact SSN-like patterns if they appear in model output.
        return re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[REDACTED-SSN]', response_text)

    def _has_emergency_signal(self, normalized_prompt: str) -> bool:
        for hint_group in self._EMERGENCY_HINT_GROUPS:
            if all(hint in normalized_prompt for hint in hint_group):
                return True
        return False

    @staticmethod
    def _is_out_of_scope(normalized_prompt: str) -> bool:
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


class DefaultPlanner:
    def build_messages(
        self,
        *,
        system_prompt: str,
        prompt: str,
        history: list[dict[str, str]] | None,
    ) -> list[dict[str, object]]:
        messages: list[dict[str, object]] = [
            {'role': 'system', 'content': system_prompt},
        ]

        for message in history or []:
            role = message.get('role')
            content = message.get('content', '')
            if role in {'user', 'assistant'} and isinstance(content, str) and content:
                messages.append({'role': role, 'content': content})

        messages.append({'role': 'user', 'content': prompt})
        return messages


class ToolExecutionSandbox:
    def __init__(
        self,
        *,
        max_tool_rounds: int,
        max_tool_calls: int | None,
        timeout_budget_ms: int,
        per_tool_limit: int,
    ) -> None:
        self.max_tool_rounds = max(1, max_tool_rounds)
        self.max_tool_calls = None if max_tool_calls is None else max(1, max_tool_calls)
        self.timeout_budget_ms = max(1000, timeout_budget_ms)
        self.per_tool_limit = max(1, per_tool_limit)
        self._started_at = monotonic()
        self._total_tool_calls = 0
        self._per_tool_calls: dict[str, int] = {}

    def has_time_budget(self) -> bool:
        return (monotonic() - self._started_at) * 1000 <= self.timeout_budget_ms

    def can_accept_calls(self, call_count: int) -> bool:
        if self.max_tool_calls is None:
            return True
        return self._total_tool_calls + call_count <= self.max_tool_calls

    def register_call(self, tool_name: str) -> None:
        self._total_tool_calls += 1
        current = self._per_tool_calls.get(tool_name, 0) + 1
        self._per_tool_calls[tool_name] = current

    def tool_is_rate_limited(self, tool_name: str) -> bool:
        return self._per_tool_calls.get(tool_name, 0) > self.per_tool_limit


class InMemoryTurnMemoryManager:
    def __init__(self, max_turns: int = 20) -> None:
        self._max_turns = max(1, max_turns)
        self._turns: list[dict[str, object]] = []

    def remember(self, payload: dict[str, object]) -> None:
        self._turns.append(payload)
        if len(self._turns) > self._max_turns:
            self._turns = self._turns[-self._max_turns :]


class StructuredAuditLogger:
    def log_turn_event(self, *, event: str, prompt: str, data: dict[str, object]) -> None:
        trace_payload = {
            'event': event,
            'prompt_hash': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
            'data': data,
        }
        logger.info('ai.audit.trace %s', json.dumps(trace_payload, sort_keys=True, default=str))
