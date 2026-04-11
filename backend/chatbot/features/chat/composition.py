from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from chatbot.features.chat.application.use_cases.delete_chat_session import DeleteChatSessionUseCase
from chatbot.features.chat.application.use_cases.get_chat_history import (
    GetChatHistoryUseCase,
)
from chatbot.features.chat.application.use_cases.get_chat_history_sync import (
    GetChatHistorySyncUseCase,
)
from chatbot.features.chat.application.use_cases.prepare_chat_turn import PrepareChatTurnUseCase
from chatbot.features.chat.models import ChatMessage
from chatbot.features.chat.infrastructure.unit_of_work.django_chat import DjangoChatUnitOfWork
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


def build_get_chat_history_sync_use_case() -> GetChatHistorySyncUseCase:
    return GetChatHistorySyncUseCase(uow=DjangoChatUnitOfWork())


def build_save_assistant_response_fn(
    *, session: Any,
) -> Callable[[Iterable[str]], None]:
    uow = DjangoChatUnitOfWork()

    def _save(chunks: Iterable[str]) -> None:
        content = ''.join(chunks)
        if not content:
            return
        validated_content = require_non_blank_text(content, field='assistant_response')
        uow.create_assistant_message(
            session=session,
            content=validated_content,
            message_kind=ChatMessage.MessageKind.TEXT,
        )

    return _save
