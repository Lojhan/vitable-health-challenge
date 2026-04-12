from typing import Any, cast


def _model_pk(instance: object) -> int:
    return cast(int, cast(Any, instance).pk)


def _build_session_title(session: Any) -> str:
    annotated_title = getattr(session, 'summary_title', None)
    if isinstance(annotated_title, str) and annotated_title.strip():
        normalized_title = ' '.join(annotated_title.split())
        if normalized_title:
            return normalized_title[:42]

    prefetched_messages = getattr(session, '_prefetched_objects_cache', {}).get('messages')
    if prefetched_messages is not None:
        first_user_message = next(
            (
                message.content
                for message in sorted(
                    prefetched_messages,
                    key=lambda message: (message.created_at, message.id),
                )
                if message.role == 'user'
            ),
            None,
        )
    else:
        first_user_message = None

    if not first_user_message:
        return 'New conversation'

    normalized = ' '.join(first_user_message.split())
    if not normalized:
        return 'New conversation'

    return normalized[:42]


def _serialize_chat_session_summary(session: Any) -> dict[str, object]:
    return {
        'id': _model_pk(session),
        'title': _build_session_title(session),
        'created_at': session.created_at.isoformat(),
        'updated_at': session.updated_at.isoformat(),
    }


def _serialize_chat_session(session: Any) -> dict[str, object]:
    prefetched_messages = getattr(session, '_prefetched_objects_cache', {}).get('messages')
    if prefetched_messages is not None:
        ordered_messages = sorted(
            prefetched_messages,
            key=lambda message: (message.created_at, message.id),
        )
    else:
        ordered_messages = []

    return {
        'id': _model_pk(session),
        'title': _build_session_title(session),
        'created_at': session.created_at.isoformat(),
        'updated_at': session.updated_at.isoformat(),
        'messages': [
            {
                'role': message.role,
                'message_kind': message.message_kind,
                'content': message.content,
                'created_at': message.created_at.isoformat(),
            }
            for message in ordered_messages
        ],
    }
