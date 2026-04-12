from __future__ import annotations

from collections.abc import Callable

from chatbot.features.chat.application.contracts import ChatUnitOfWork
from chatbot.features.core.application.contracts import BaseUseCase


class GetChatHistoryUseCase(BaseUseCase):
    def __init__(
        self,
        *,
        uow: ChatUnitOfWork,
        serialize_session: Callable[[object], dict[str, object]],
    ) -> None:
        self._uow = uow
        self._serialize_session = serialize_session

    def execute(
        self,
        *,
        user_id: int,
        cursor: str | None,
        page_size: int,
    ) -> dict[str, object]:
        sessions, next_cursor, has_more = self._uow.list_user_session_summaries_page(
            user_id=user_id,
            cursor=cursor,
            page_size=page_size,
        )
        return {
            'sessions': [self._serialize_session(session) for session in sessions],
            'next_cursor': next_cursor,
            'has_more': has_more,
        }
