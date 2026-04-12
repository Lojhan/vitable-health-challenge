from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import TracebackType
from typing import Any

from django.db import IntegrityError, transaction

from chatbot.features.chat.models import ChatMessage, ChatSession, StructuredInteraction
from chatbot.features.core.application.contracts import BaseUnitOfWork


class DjangoChatUnitOfWork(BaseUnitOfWork):
    """Infrastructure implementation of chat persistence operations using Django ORM."""

    def __enter__(self) -> DjangoChatUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        pass

    def get_or_create_session(self, *, user: Any, session_id: int | None) -> ChatSession:
        if session_id is not None:
            session = ChatSession.objects.filter(id=session_id, user_id=user.id).first()
            if session is not None:
                return session
        return ChatSession.objects.create(user=user)

    def create_user_messages(
        self,
        *,
        session: ChatSession,
        contents: list[str],
        request_id: str | None = None,
    ) -> list[ChatMessage]:
        created_messages: list[ChatMessage] = []
        for index, content in enumerate(contents):
            message_request_id = request_id if index == 0 else None
            if message_request_id is None:
                created_messages.append(
                    ChatMessage.objects.create(
                        session=session,
                        role=ChatMessage.ROLE_USER,
                        message_kind=ChatMessage.MessageKind.TEXT,
                        content=content,
                    )
                )
                continue

            try:
                message, _ = ChatMessage.objects.get_or_create(
                    session=session,
                    role=ChatMessage.ROLE_USER,
                    request_id=message_request_id,
                    defaults={
                        'content': content,
                        'message_kind': ChatMessage.MessageKind.TEXT,
                    },
                )
            except IntegrityError:
                message = ChatMessage.objects.get(
                    session=session,
                    role=ChatMessage.ROLE_USER,
                    request_id=message_request_id,
                )
            created_messages.append(message)

        return created_messages

    def user_message_exists_with_request_id(
        self,
        *,
        session: ChatSession,
        request_id: str,
    ) -> bool:
        return ChatMessage.objects.filter(
            session=session,
            role=ChatMessage.ROLE_USER,
            request_id=request_id,
        ).exists()

    @contextmanager
    def session_critical_section(self, *, session_id: int) -> Iterator[ChatSession]:
        with transaction.atomic():
            locked_session = ChatSession.objects.select_for_update().get(id=session_id)
            yield locked_session

    def get_ordered_messages(self, *, session: ChatSession) -> list[ChatMessage]:
        return list(
            ChatMessage.objects.filter(session=session)
            .only('id', 'role', 'message_kind', 'content', 'created_at')
            .order_by('created_at', 'id')
        )

    def create_assistant_message(
        self,
        *,
        session: ChatSession,
        content: str,
        message_kind: str,
    ) -> None:
        ChatMessage.objects.create(
            session=session,
            role=ChatMessage.ROLE_ASSISTANT,
            message_kind=message_kind,
            content=content,
        )

    def delete_session(self, *, user_id: int, session_id: int) -> bool:
        deleted_count, _ = ChatSession.objects.filter(
            id=session_id,
            user_id=user_id,
        ).delete()
        return deleted_count > 0

    def list_user_sessions_prefetched(self, *, user_id: int) -> list[ChatSession]:
        return list(
            ChatSession.objects.filter(user_id=user_id)
            .prefetch_related('messages')
            .order_by('-updated_at', '-id')
        )

    def get_history_sync_payload(self, *, user_id: int) -> dict[str, object]:
        sessions = ChatSession.objects.filter(user_id=user_id)
        latest_updated_at = sessions.values_list('updated_at', flat=True).first()
        message_count = ChatMessage.objects.filter(session__user_id=user_id).count()

        return {
            'latest_updated_at': (
                latest_updated_at.isoformat() if latest_updated_at is not None else None
            ),
            'session_count': sessions.count(),
            'message_count': message_count,
        }

    def get_structured_interaction_selection(
        self,
        *,
        user_id: int,
        interaction_id: str,
    ) -> dict[str, Any] | None:
        row = StructuredInteraction.objects.filter(
            user_id=user_id,
            interaction_id=interaction_id,
        ).first()
        return row.selection if row is not None else None

    def save_structured_interaction_selection(
        self,
        *,
        user_id: int,
        interaction_id: str,
        kind: str,
        selection: dict[str, Any],
    ) -> dict[str, Any]:
        row, _ = StructuredInteraction.objects.update_or_create(
            user_id=user_id,
            interaction_id=interaction_id,
            defaults={
                'kind': kind,
                'selection': selection,
            },
        )
        return row.selection
