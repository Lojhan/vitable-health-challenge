from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from types import TracebackType
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import OuterRef, Q, Subquery
from django.utils.dateparse import parse_datetime

from chatbot.features.chat.models import ChatMessage, ChatSession, StructuredInteraction
from chatbot.features.core.application.contracts import BaseUnitOfWork


class DjangoChatUnitOfWork(BaseUnitOfWork):
    """Infrastructure implementation of chat persistence operations using Django ORM."""

    @staticmethod
    def _encode_history_cursor(*, updated_at: datetime, session_id: int) -> str:
        payload = json.dumps(
            {
                'updated_at': updated_at.isoformat(),
                'id': session_id,
            },
            separators=(',', ':'),
        ).encode('utf-8')
        return base64.urlsafe_b64encode(payload).decode('utf-8').rstrip('=')

    @staticmethod
    def _decode_history_cursor(cursor: str) -> tuple[datetime, int] | None:
        normalized = cursor.strip()
        if not normalized:
            return None

        try:
            padding = '=' * (-len(normalized) % 4)
            payload = base64.urlsafe_b64decode(f'{normalized}{padding}'.encode('utf-8'))
            parsed = json.loads(payload.decode('utf-8'))
        except (ValueError, json.JSONDecodeError):
            return None

        updated_at_raw = parsed.get('updated_at')
        session_id_raw = parsed.get('id')
        if not isinstance(updated_at_raw, str) or not isinstance(session_id_raw, int):
            return None

        updated_at = parse_datetime(updated_at_raw)
        if updated_at is None:
            return None

        return updated_at, session_id_raw

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

    def list_user_session_summaries_page(
        self,
        *,
        user_id: int,
        cursor: str | None,
        page_size: int,
    ) -> tuple[list[ChatSession], str | None, bool]:
        first_user_message = ChatMessage.objects.filter(
            session_id=OuterRef('pk'),
            role=ChatMessage.ROLE_USER,
        ).order_by('created_at', 'id')

        query = ChatSession.objects.filter(user_id=user_id).annotate(
            summary_title=Subquery(first_user_message.values('content')[:1]),
        )

        decoded_cursor = self._decode_history_cursor(cursor) if cursor is not None else None
        if decoded_cursor is not None:
            cursor_updated_at, cursor_session_id = decoded_cursor
            query = query.filter(
                Q(updated_at__lt=cursor_updated_at)
                | Q(updated_at=cursor_updated_at, id__lt=cursor_session_id)
            )

        ordered_sessions = list(query.order_by('-updated_at', '-id')[: page_size + 1])
        page = ordered_sessions[:page_size]
        has_more = len(ordered_sessions) > page_size
        next_cursor = None
        if has_more and page:
            last_session = page[-1]
            next_cursor = self._encode_history_cursor(
                updated_at=last_session.updated_at,
                session_id=last_session.id,
            )

        return page, next_cursor, has_more

    def get_user_session_prefetched(self, *, user_id: int, session_id: int) -> ChatSession | None:
        return (
            ChatSession.objects.filter(user_id=user_id, id=session_id)
            .prefetch_related('messages')
            .first()
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
