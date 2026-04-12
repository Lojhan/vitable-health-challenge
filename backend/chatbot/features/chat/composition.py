from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Any

from chatbot.features.chat.application.use_cases.delete_chat_session import DeleteChatSessionUseCase
from chatbot.features.chat.application.use_cases.get_chat_history import (
    GetChatHistoryUseCase,
)
from chatbot.features.chat.application.use_cases.get_chat_session import (
    GetChatSessionUseCase,
)
from chatbot.features.chat.application.use_cases.get_chat_history_sync import (
    GetChatHistorySyncUseCase,
)
from chatbot.features.chat.application.use_cases.get_structured_interaction import (
    GetStructuredInteractionUseCase,
)
from chatbot.features.chat.application.use_cases.prepare_chat_turn import PrepareChatTurnUseCase
from chatbot.features.chat.application.use_cases.save_structured_interaction import (
    SaveStructuredInteractionUseCase,
)
from chatbot.features.chat.infrastructure.unit_of_work.django_chat import DjangoChatUnitOfWork
from chatbot.features.chat.models import ChatMessage
from chatbot.features.chat.stream_protocol import (
    PREFIX_ERROR,
    PREFIX_TEXT_DELTA,
    PREFIX_TOOL_RESULT,
)
from chatbot.features.core.domain.validation import require_non_blank_text


def build_prepare_chat_turn_use_case(*, debounce_window_seconds: float) -> PrepareChatTurnUseCase:
    return PrepareChatTurnUseCase(
        debounce_window_seconds=debounce_window_seconds,
        uow=DjangoChatUnitOfWork(),
    )


def build_delete_chat_session_use_case() -> DeleteChatSessionUseCase:
    return DeleteChatSessionUseCase(uow=DjangoChatUnitOfWork())


def build_get_chat_history_use_case(
    *, serialize_session: Callable[[object], dict[str, object]],
) -> GetChatHistoryUseCase:
    return GetChatHistoryUseCase(
        uow=DjangoChatUnitOfWork(),
        serialize_session=serialize_session,
    )


def build_get_chat_session_use_case(
    *, serialize_session: Callable[[object], dict[str, object]],
) -> GetChatSessionUseCase:
    return GetChatSessionUseCase(
        uow=DjangoChatUnitOfWork(),
        serialize_session=serialize_session,
    )


def build_get_chat_history_sync_use_case() -> GetChatHistorySyncUseCase:
    return GetChatHistorySyncUseCase(uow=DjangoChatUnitOfWork())


def build_get_structured_interaction_use_case() -> GetStructuredInteractionUseCase:
    return GetStructuredInteractionUseCase(uow=DjangoChatUnitOfWork())


def build_save_structured_interaction_use_case() -> SaveStructuredInteractionUseCase:
    return SaveStructuredInteractionUseCase(uow=DjangoChatUnitOfWork())


def build_save_assistant_response_fn(
    *, session: Any,
) -> Callable[[Iterable[Any]], None]:
    uow = DjangoChatUnitOfWork()

    _UI_KIND_TO_MESSAGE_KIND: dict[str, str] = {
        'providers': ChatMessage.MessageKind.PROVIDERS,
        'availability': ChatMessage.MessageKind.AVAILABILITY,
        'appointments': ChatMessage.MessageKind.APPOINTMENTS,
    }

    def _parse_protocol_line(raw: str) -> tuple[str, object] | None:
        """Parse ``{prefix}:{json}\\n`` → (prefix, payload)."""
        stripped = raw.strip()
        if len(stripped) < 2 or stripped[1] != ':':
            return None
        prefix = stripped[0]
        try:
            payload = json.loads(stripped[2:])
        except (json.JSONDecodeError, IndexError):
            payload = stripped[2:]
        return prefix, payload

    def _save(chunks: Iterable[Any]) -> None:
        text_accumulator: list[str] = []

        def _flush_text() -> None:
            if not text_accumulator:
                return
            merged = ''.join(text_accumulator).strip()
            text_accumulator.clear()
            if not merged:
                return
            validated = require_non_blank_text(merged, field='assistant_response')
            uow.create_assistant_message(
                session=session,
                content=validated,
                message_kind=ChatMessage.MessageKind.TEXT,
            )

        for chunk in chunks:
            if not isinstance(chunk, str):
                continue

            parsed = _parse_protocol_line(chunk)
            if parsed is None:
                # Legacy plain-text chunk
                text_accumulator.append(chunk)
                continue

            prefix, payload = parsed

            if prefix == PREFIX_TEXT_DELTA:
                text_accumulator.append(str(payload))

            elif prefix == PREFIX_TOOL_RESULT:
                # Flush accumulated text before structured message
                _flush_text()
                if isinstance(payload, dict):
                    ui_kind = str(payload.get('ui_kind', '')).strip().lower()
                    result = payload.get('result', payload)
                    if isinstance(result, dict):
                        result_state = str(result.get('ui_state', 'final')).strip().lower()
                        if result_state and result_state != 'final':
                            continue
                    message_kind = _UI_KIND_TO_MESSAGE_KIND.get(
                        ui_kind, ChatMessage.MessageKind.JSON,
                    )
                    content = json.dumps(result, default=str) if not isinstance(result, str) else result
                    normalized = content.strip()
                    if normalized:
                        validated = require_non_blank_text(normalized, field='assistant_response')
                        uow.create_assistant_message(
                            session=session,
                            content=validated,
                            message_kind=message_kind,
                        )

            elif prefix == PREFIX_ERROR:
                _flush_text()
                error_text = str(payload).strip()
                if error_text:
                    validated = require_non_blank_text(error_text, field='assistant_response')
                    uow.create_assistant_message(
                        session=session,
                        content=validated,
                        message_kind=ChatMessage.MessageKind.TEXT,
                    )

            # Prefixes s, 8, d — not persisted

        _flush_text()

    return _save
