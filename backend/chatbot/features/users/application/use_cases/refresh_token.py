from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from ninja_jwt.exceptions import TokenError
from ninja_jwt.tokens import RefreshToken

from chatbot.features.core.application.contracts import BaseUseCase
from chatbot.features.users.application.token import TokenUnitOfWork


class InvalidRefreshTokenError(Exception):
    """Raised when the provided refresh token is missing, invalid, or expired."""


@dataclass(frozen=True)
class RefreshTokenResult:
    access: str
    refresh: str


class RefreshTokenUseCase(BaseUseCase):
    def __init__(self, uow: TokenUnitOfWork) -> None:
        self._uow = uow

    def execute(self, *, refresh_token_str: str) -> RefreshTokenResult:
        try:
            incoming = RefreshToken(refresh_token_str)
            user_id = incoming.get('user_id')
            if user_id is None:
                raise InvalidRefreshTokenError('Missing user_id in token')

            user = self._uow.get_user_by_id(int(user_id))
            new_refresh = RefreshToken.for_user(user)
            typed = cast(Any, new_refresh)
            return RefreshTokenResult(
                access=str(typed.access_token),
                refresh=str(new_refresh),
            )
        except (TokenError, ValueError, Exception) as exc:
            if isinstance(exc, InvalidRefreshTokenError):
                raise
            raise InvalidRefreshTokenError(str(exc)) from exc
