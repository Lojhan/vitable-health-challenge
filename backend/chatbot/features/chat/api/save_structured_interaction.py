from typing import Any, cast

from ninja import Router
from ninja_jwt.authentication import JWTAuth

from chatbot.features.chat.api.structured_interaction_schemas import (
    StructuredInteractionResponseSchema,
    StructuredInteractionSaveSchema,
)
from chatbot.features.chat.composition import build_save_structured_interaction_use_case
from chatbot.features.core.auth_context import get_authenticated_user

router = Router()


@router.post(
    '/chat/structured-interactions',
    auth=JWTAuth(),
    response=StructuredInteractionResponseSchema,
)
def save_structured_interaction(
    request: Any,
    payload: StructuredInteractionSaveSchema,
) -> dict[str, object]:
    user = get_authenticated_user(request)
    return build_save_structured_interaction_use_case().execute(
        user_id=cast(int, user.id),
        interaction_id=payload.interaction_id,
        kind=payload.kind,
        selection=payload.selection,
    )