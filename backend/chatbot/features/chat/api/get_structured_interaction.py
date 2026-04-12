from typing import Any, cast

from ninja import Router
from ninja_jwt.authentication import JWTAuth

from chatbot.features.chat.api.structured_interaction_schemas import (
    StructuredInteractionResponseSchema,
)
from chatbot.features.chat.composition import build_get_structured_interaction_use_case
from chatbot.features.core.auth_context import get_authenticated_user

router = Router()


@router.get(
    '/chat/structured-interactions/{interaction_id}',
    auth=JWTAuth(),
    response=StructuredInteractionResponseSchema,
)
def get_structured_interaction(request: Any, interaction_id: str) -> dict[str, object]:
    user = get_authenticated_user(request)
    return build_get_structured_interaction_use_case().execute(
        user_id=cast(int, user.id),
        interaction_id=interaction_id,
    )