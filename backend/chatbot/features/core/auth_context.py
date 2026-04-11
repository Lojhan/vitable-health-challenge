from typing import Any, cast

from django.contrib.auth import get_user_model
from ninja_jwt.tokens import AccessToken


def _get_user_from_jwt(request: object) -> Any | None:
    headers = getattr(request, 'headers', {}) or {}
    authorization_header = headers.get('Authorization', '')
    if not authorization_header.startswith('Bearer '):
        return None

    token_value = authorization_header.split(' ', maxsplit=1)[1]
    token = AccessToken(token_value)
    user_id = token.get('user_id')
    if user_id is None:
        return None

    user_model = get_user_model()
    return user_model.objects.get(id=user_id)


def get_authenticated_user(request: object) -> Any:
    request_user = getattr(request, 'user', None)
    if getattr(request_user, 'is_authenticated', False):
        user_model = get_user_model()
        request_user_id = getattr(request_user, 'pk', None)
        if request_user_id is None:
            raise ValueError('Authenticated request user is missing a primary key.')
        return cast(Any, user_model.objects.get(id=request_user_id))

    user = _get_user_from_jwt(request)
    if user is None:
        raise ValueError('Authenticated user could not be resolved from request context.')
    return cast(Any, user)
