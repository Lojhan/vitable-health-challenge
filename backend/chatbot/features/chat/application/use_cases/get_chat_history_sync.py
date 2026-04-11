from __future__ import annotations

from chatbot.features.chat.application.contracts import ChatUnitOfWork
from chatbot.features.core.application.contracts import BaseUseCase


class GetChatHistorySyncUseCase(BaseUseCase):
    def __init__(self, *, uow: ChatUnitOfWork) -> None:
        self._uow = uow

    def execute(self, *, user_id: int) -> dict[str, object]:
        return self._uow.get_history_sync_payload(user_id=user_id)
