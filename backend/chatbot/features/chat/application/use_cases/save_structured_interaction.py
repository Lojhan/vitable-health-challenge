from datetime import UTC, datetime
from typing import Any

from chatbot.features.chat.application.contracts import ChatUnitOfWork
from chatbot.features.core.application.contracts import BaseUseCase


class SaveStructuredInteractionUseCase(BaseUseCase):
    def __init__(self, *, uow: ChatUnitOfWork) -> None:
        self._uow = uow

    def execute(
        self,
        *,
        user_id: int,
        interaction_id: str,
        kind: str,
        selection: dict[str, Any],
    ) -> dict[str, object]:
        normalized_id = interaction_id.strip()
        if not normalized_id or not selection:
            return {'interaction_id': normalized_id, 'selection': None}

        selection_data = {
            'kind': kind,
            **selection,
            'saved_at': datetime.now(UTC).isoformat(),
        }
        persisted_selection = self._uow.save_structured_interaction_selection(
            user_id=user_id,
            interaction_id=normalized_id,
            kind=kind,
            selection=selection_data,
        )
        return {
            'interaction_id': normalized_id,
            'selection': persisted_selection,
        }