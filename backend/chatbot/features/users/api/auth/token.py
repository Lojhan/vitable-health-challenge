import logging
from typing import Any, cast

from django.contrib.auth import authenticate
from ninja import Router, Schema
from ninja.responses import Status
from ninja_jwt.tokens import RefreshToken
from pydantic import ValidationInfo, field_validator

from chatbot.features.core.api.validation import ValidationErrorResponseSchema
from chatbot.features.core.domain.validation import require_non_blank_text
from chatbot.features.core.observability import (
    AuditEventData,
    StructuredLogger,
    create_audit_event,
    generate_request_id,
    set_request_id,
    set_user_id,
)
from chatbot.features.users.application.use_cases.refresh_token import InvalidRefreshTokenError
from chatbot.features.users.composition import build_refresh_token_use_case

router = Router()
logger = logging.getLogger(__name__)
obs_logger = StructuredLogger(__name__)


class TokenRequestSchema(Schema):
    username: str
    password: str

    @field_validator('username', 'password')
    @classmethod
    def validate_required_text(
        cls: type['TokenRequestSchema'],
        value: str,
        info: ValidationInfo,
    ) -> str:
        return require_non_blank_text(value, field=info.field_name)


class TokenResponseSchema(Schema):
    access: str
    refresh: str


class AuthErrorSchema(Schema):
    detail: str


class RefreshRequestSchema(Schema):
    refresh: str

    @field_validator('refresh')
    @classmethod
    def validate_refresh(cls: type['RefreshRequestSchema'], value: str) -> str:
        return require_non_blank_text(value, field='refresh')


@router.post(
    '/token',
    response={200: TokenResponseSchema, 401: AuthErrorSchema, 422: ValidationErrorResponseSchema},
)
def obtain_token(request: Any, payload: TokenRequestSchema) -> Status | dict[str, str]:
    request_id = generate_request_id()
    set_request_id(request_id)
    
    user = authenticate(username=payload.username, password=payload.password)
    if user is None:
        obs_logger.warning(
            'auth.login.failed',
            reason_code='INVALID_CREDENTIALS',
            details={'username': payload.username},
        )
        create_audit_event(AuditEventData(
            event_type='AUTH_FAILURE',
            severity='WARNING',
            action='login_attempt',
            reason_code='INVALID_CREDENTIALS',
            details={'username': payload.username},
        ))
        return Status(401, {'detail': 'Invalid credentials'})

    set_user_id(user.id)
    refresh = RefreshToken.for_user(user)
    typed_refresh = cast(Any, refresh)
    
    obs_logger.info(
        'auth.login.success',
        details={'user_id': user.id},
    )
    create_audit_event(AuditEventData(
        event_type='AUTH_LOGIN',
        severity='INFO',
        resource_type='user',
        resource_id=str(user.id),
        action='login_successful',
        details={},
    ))
    
    return {'access': str(typed_refresh.access_token), 'refresh': str(refresh)}


@router.post(
    '/refresh',
    response={200: TokenResponseSchema, 401: AuthErrorSchema, 422: ValidationErrorResponseSchema},
)
def refresh_token(request: Any, payload: RefreshRequestSchema) -> Status | dict[str, str]:
    use_case = build_refresh_token_use_case()
    try:
        logger.debug('Attempting to refresh access token with provided refresh token')
        logger.debug(f'Refresh token payload: {payload.refresh}')
        result = use_case.execute(refresh_token_str=payload.refresh)
        return {'access': result.access, 'refresh': result.refresh}
    except InvalidRefreshTokenError:
        logger.warning('auth.refresh.invalid_token', exc_info=True)
        return Status(401, {'detail': 'Invalid refresh token'})
