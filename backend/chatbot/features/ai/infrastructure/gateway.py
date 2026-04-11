from __future__ import annotations

import logging
from time import monotonic
from typing import Any, Protocol, cast
from uuid import uuid4

from openai import APIStatusError, AsyncOpenAI

logger = logging.getLogger(__name__)


class LlmGateway(Protocol):
    async def create_chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, object]],
        tools: list[dict],
        max_tokens: int,
    ) -> object: ...


class OpenRouterChatGateway:
    def __init__(self, client: AsyncOpenAI) -> None:
        self._client = client

    async def create_chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, object]],
        tools: list[dict],
        max_tokens: int,
    ) -> object:
        return await self._client.chat.completions.create(
            model=model,
            messages=cast(Any, messages),
            tools=cast(Any, tools),
            max_tokens=max_tokens,
        )


class GatewayCircuitBreaker:
    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        recovery_timeout_seconds: int = 30,
    ) -> None:
        self._failure_threshold = max(1, failure_threshold)
        self._recovery_timeout_seconds = max(1, recovery_timeout_seconds)
        self._failures = 0
        self._opened_at: float | None = None

    def can_execute(self) -> bool:
        if self._opened_at is None:
            return True
        return (monotonic() - self._opened_at) >= self._recovery_timeout_seconds

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._failure_threshold:
            self._opened_at = monotonic()


class ResilientGateway:
    def __init__(
        self,
        *,
        gateways: list[LlmGateway],
        max_retries: int = 1,
        circuit_breakers: list[GatewayCircuitBreaker] | None = None,
    ) -> None:
        if not gateways:
            raise ValueError('At least one gateway is required')
        self._gateways = gateways
        self._max_retries = max(0, max_retries)
        self._breakers = circuit_breakers or [GatewayCircuitBreaker() for _ in gateways]
        if len(self._breakers) != len(self._gateways):
            raise ValueError('Each gateway must have a corresponding circuit breaker')

    async def create_chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, object]],
        tools: list[dict],
        max_tokens: int,
    ) -> object:
        last_error: Exception | None = None

        for gateway, breaker in zip(self._gateways, self._breakers, strict=False):
            if not breaker.can_execute():
                continue

            for attempt in range(self._max_retries + 1):
                correlation_id = str(uuid4())
                try:
                    response = await gateway.create_chat_completion(
                        model=model,
                        messages=messages,
                        tools=tools,
                        max_tokens=max_tokens,
                    )
                    breaker.record_success()
                    return response
                except Exception as error:
                    last_error = error
                    breaker.record_failure()
                    logger.warning(
                        'ai.gateway.call_failed',
                        extra={
                            'correlation_id': correlation_id,
                            'attempt': attempt + 1,
                            'max_retries': self._max_retries,
                            'error_type': type(error).__name__,
                        },
                        exc_info=True,
                    )
                    if attempt >= self._max_retries or not self._is_retryable(error):
                        break

        if last_error is not None:
            raise last_error
        raise RuntimeError('No available model gateway')

    @staticmethod
    def _is_retryable(error: Exception) -> bool:
        if isinstance(error, (TimeoutError, ConnectionError, RuntimeError)):
            return True
        if isinstance(error, APIStatusError):
            status = getattr(error, 'status_code', None)
            return status in {408, 409, 429} or (status is not None and status >= 500)
        return False
