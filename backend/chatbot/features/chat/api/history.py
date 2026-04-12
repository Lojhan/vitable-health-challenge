from typing import Any, cast

from ninja import Router
from ninja_jwt.authentication import JWTAuth

from chatbot.features.chat.api.history_schemas import (
    ChatHistoryResponseSchema,
    ChatHistorySyncSchema,
)
from chatbot.features.chat.api.utils import _serialize_chat_session_summary
from chatbot.features.chat.composition import (
    build_get_chat_history_sync_use_case,
    build_get_chat_history_use_case,
)
from chatbot.features.core.auth_context import get_authenticated_user

router = Router()


@router.get('/chat/history', auth=JWTAuth(), response=ChatHistoryResponseSchema)
def get_chat_history(
    request: Any,
    cursor: str | None = None,
    page_size: int = 20,
) -> dict[str, object]:
    user = get_authenticated_user(request)
    normalized_page_size = max(1, min(page_size, 50))
    return build_get_chat_history_use_case(
        serialize_session=_serialize_chat_session_summary,
    ).execute(
        user_id=cast(int, user.id),
        cursor=cursor,
        page_size=normalized_page_size,
    )


@router.get('/chat/history-sync', auth=JWTAuth(), response=ChatHistorySyncSchema)
def get_chat_history_sync(request: Any) -> dict[str, object]:
    user = get_authenticated_user(request)
    return build_get_chat_history_sync_use_case().execute(user_id=cast(int, user.id))
