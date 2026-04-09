from typing import Any, cast

from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from ninja import Router, Schema
from ninja.responses import Status
from ninja_jwt.tokens import RefreshToken

router = Router()


class TokenRequestSchema(Schema):
    username: str
    password: str


class TokenResponseSchema(Schema):
    access: str
    refresh: str


class AuthErrorSchema(Schema):
    detail: str


class RefreshRequestSchema(Schema):
    refresh: str


@router.post('/token', response={200: TokenResponseSchema, 401: AuthErrorSchema})
def obtain_token(request, payload: TokenRequestSchema):
    user = authenticate(username=payload.username, password=payload.password)
    if user is None:
        return Status(401, {'detail': 'Invalid credentials'})

    refresh = RefreshToken.for_user(user)
    typed_refresh = cast(Any, refresh)
    return {'access': str(typed_refresh.access_token), 'refresh': str(refresh)}


@router.post('/refresh', response={200: TokenResponseSchema, 401: AuthErrorSchema})
def refresh_token(request, payload: RefreshRequestSchema):
    try:
        incoming_refresh = RefreshToken(payload.refresh)
        user_id = incoming_refresh.get('user_id')
        if user_id is None:
            raise ValueError('Missing user_id')

        user_model = get_user_model()
        user = user_model.objects.get(id=user_id)
        new_refresh = RefreshToken.for_user(user)
        typed_refresh = cast(Any, new_refresh)
        return {
            'access': str(typed_refresh.access_token),
            'refresh': str(new_refresh),
        }
    except Exception:
        return Status(401, {'detail': 'Invalid refresh token'})
