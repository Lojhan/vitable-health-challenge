from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from chatbot.features.chat.application.contracts import ChatUnitOfWork
from chatbot.features.chat.message_burst import (
    build_prompt_from_pending_user_messages,
    should_defer_response,
    split_incoming_message_payload,
)
from chatbot.features.core.application.contracts import BaseUseCase
from chatbot.features.core.domain.validation import require_non_blank_text

_ROLE_ASSISTANT = 'assistant'
_ROLE_USER = 'user'


@dataclass(frozen=True)
class PreparedChatTurn:
    session: Any
    history: list[dict[str, str]]
    prompt_for_agent: str | None
    merged_into_previous_response: bool


class PrepareChatTurnUseCase(BaseUseCase):
    def __init__(self, *, debounce_window_seconds: float, uow: ChatUnitOfWork) -> None:
        self._debounce_window_seconds = debounce_window_seconds
        self._uow = uow

    def execute(
        self,
        *,
        user: Any,
        message: str,
        session_id: int | None,
        request_id: str | None = None,
    ) -> PreparedChatTurn:
        session = self._uow.get_or_create_session(user=user, session_id=session_id)
        normalized_request_id = (
            require_non_blank_text(request_id, field='request_id')
            if request_id is not None
            else None
        )

        with self._uow.session_critical_section(session_id=self._model_pk(session)) as locked_session:
            if (
                normalized_request_id is not None
                and self._uow.user_message_exists_with_request_id(
                    session=locked_session,
                    request_id=normalized_request_id,
                )
            ):
                return PreparedChatTurn(
                    session=locked_session,
                    history=[],
                    prompt_for_agent=None,
                    merged_into_previous_response=True,
                )

            incoming_messages = split_incoming_message_payload(message)
            if not incoming_messages:
                incoming_messages = [require_non_blank_text(message, field='message')]

            validated_incoming_messages = [
                require_non_blank_text(content, field='message')
                for content in incoming_messages
            ]

            created_messages = self._uow.create_user_messages(
                session=locked_session,
                contents=validated_incoming_messages,
                request_id=normalized_request_id,
            )
            request_message = created_messages[-1]

            ordered_messages = self._uow.get_ordered_messages(session=locked_session)
            history, pending_user_messages = self._split_history_and_pending(ordered_messages)

            if should_defer_response(pending_user_messages):
                return PreparedChatTurn(
                    session=locked_session,
                    history=history,
                    prompt_for_agent=None,
                    merged_into_previous_response=True,
                )

            if self._model_pk(request_message) not in {
                self._model_pk(m)
                for m in pending_user_messages
            }:
                return PreparedChatTurn(
                    session=locked_session,
                    history=history,
                    prompt_for_agent=None,
                    merged_into_previous_response=True,
                )

            prompt_for_agent = build_prompt_from_pending_user_messages(
                pending_user_messages,
            )

            return PreparedChatTurn(
                session=locked_session,
                history=history,
                prompt_for_agent=prompt_for_agent,
                merged_into_previous_response=False,
            )

    @staticmethod
    def _model_pk(instance: Any) -> int:
        return cast(int, cast(Any, instance).pk)

    @staticmethod
    def _split_history_and_pending(
        ordered_messages: list[Any],
    ) -> tuple[list[dict[str, str]], list[Any]]:
        last_assistant_index = -1
        for index, message in enumerate(ordered_messages):
            if message.role == _ROLE_ASSISTANT:
                last_assistant_index = index

        history_messages = ordered_messages[: last_assistant_index + 1]
        pending_user_messages = [
            message
            for message in ordered_messages[last_assistant_index + 1 :]
            if message.role == _ROLE_USER
        ]

        history_payload = [
            {'role': message.role, 'content': message.content}
            for message in history_messages
        ]
        return history_payload, pending_user_messages
