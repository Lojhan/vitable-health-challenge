from chatbot.features.chat.application.contracts import ChatUnitOfWork
from chatbot.features.core.application.contracts import BaseUseCase


class DeleteChatSessionUseCase(BaseUseCase):
    def __init__(self, *, uow: ChatUnitOfWork) -> None:
        self._uow = uow

    def execute(self, *, user_id: int, session_id: int) -> bool:
        return self._uow.delete_session(user_id=user_id, session_id=session_id)
