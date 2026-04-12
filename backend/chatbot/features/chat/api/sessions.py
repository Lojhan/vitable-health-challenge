from typing import Any, cast

from ninja_extra import Router
from ninja_jwt.authentication import JWTAuth

from chatbot.features.chat.composition import build_delete_chat_session_use_case
from chatbot.features.core.auth_context import get_authenticated_user

router = Router()

@router.delete('/chat/sessions/{session_id}', auth=JWTAuth())
def delete_chat_session(request: Any, session_id: int) -> dict[str, bool]:
    user = get_authenticated_user(request)
    deleted = build_delete_chat_session_use_case().execute(
        user_id=cast(int, user.id),
        session_id=session_id,
    )

    return {'deleted': deleted}
