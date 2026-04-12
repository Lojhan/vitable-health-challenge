from __future__ import annotations

from collections.abc import Callable

from chatbot.features.chat.application.contracts import ChatUnitOfWork
from chatbot.features.core.application.contracts import BaseUseCase


class GetChatSessionUseCase(BaseUseCase):
    def __init__(
        self,
        *,
        uow: ChatUnitOfWork,
        serialize_session: Callable[[object], dict[str, object]],
    ) -> None:
        self._uow = uow
        self._serialize_session = serialize_session

    def execute(self, *, user_id: int, session_id: int) -> dict[str, object] | None:
        session = self._uow.get_user_session_prefetched(user_id=user_id, session_id=session_id)
        if session is None:
            return None
        return self._serialize_session(session)