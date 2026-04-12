from typing import Any

from chatbot.features.chat.application.contracts import ChatUnitOfWork
from chatbot.features.core.application.contracts import BaseUseCase


class GetStructuredInteractionUseCase(BaseUseCase):
    def __init__(self, *, uow: ChatUnitOfWork) -> None:
        self._uow = uow

    def execute(self, *, user_id: int, interaction_id: str) -> dict[str, object]:
        normalized_id = interaction_id.strip()
        if not normalized_id:
            return {'interaction_id': '', 'selection': None}

        selection = self._uow.get_structured_interaction_selection(
            user_id=user_id,
            interaction_id=normalized_id,
        )
        return {
            'interaction_id': normalized_id,
            'selection': selection,
        }