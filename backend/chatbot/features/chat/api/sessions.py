from typing import Any, cast

from ninja_extra import Router
from ninja.responses import Status
from ninja_jwt.authentication import JWTAuth

from chatbot.features.chat.api.history_schemas import (
    ChatSessionResponseSchema,
    ErrorDetailSchema,
)
from chatbot.features.chat.api.utils import _serialize_chat_session
from chatbot.features.chat.composition import build_get_chat_session_use_case
from chatbot.features.chat.composition import build_delete_chat_session_use_case
from chatbot.features.core.auth_context import get_authenticated_user

router = Router()


@router.get(
    '/chat/sessions/{session_id}',
    auth=JWTAuth(),
    response={200: ChatSessionResponseSchema, 404: ErrorDetailSchema},
)
def get_chat_session(request: Any, session_id: int) -> dict[str, object] | Status:
    user = get_authenticated_user(request)
    payload = build_get_chat_session_use_case(
        serialize_session=_serialize_chat_session,
    ).execute(
        user_id=cast(int, user.id),
        session_id=session_id,
    )
    if payload is None:
        return Status(404, {'detail': 'Conversation not found.'})
    return payload

@router.delete('/chat/sessions/{session_id}', auth=JWTAuth())
def delete_chat_session(request: Any, session_id: int) -> dict[str, bool]:
    user = get_authenticated_user(request)
    deleted = build_delete_chat_session_use_case().execute(
        user_id=cast(int, user.id),
        session_id=session_id,
    )

    return {'deleted': deleted}
