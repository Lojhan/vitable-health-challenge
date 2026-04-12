from typing import Any, cast

from ninja import Router, Schema
from ninja_jwt.authentication import JWTAuth

from chatbot.features.chat.api.utils import _serialize_chat_session
from chatbot.features.chat.composition import (
    build_get_chat_history_sync_use_case,
    build_get_chat_history_use_case,
)
from chatbot.features.core.auth_context import get_authenticated_user

router = Router()

class ChatMessageResponseSchema(Schema):
    role: str
    message_kind: str
    content: str
    created_at: str


class ChatSessionResponseSchema(Schema):
    id: int
    title: str
    created_at: str
    updated_at: str
    messages: list[ChatMessageResponseSchema]


class ChatHistoryResponseSchema(Schema):
    sessions: list[ChatSessionResponseSchema]


class ChatHistorySyncSchema(Schema):
    latest_updated_at: str | None
    session_count: int
    message_count: int


@router.get('/chat/history', auth=JWTAuth(), response=ChatHistoryResponseSchema)
def get_chat_history(request: Any) -> dict[str, object]:
    user = get_authenticated_user(request)
    return build_get_chat_history_use_case(
        serialize_session=_serialize_chat_session,
    ).execute(
        user_id=cast(int, user.id),
    )


@router.get('/chat/history-sync', auth=JWTAuth(), response=ChatHistorySyncSchema)
def get_chat_history_sync(request: Any) -> dict[str, object]:
    user = get_authenticated_user(request)
    return build_get_chat_history_sync_use_case().execute(user_id=cast(int, user.id))
