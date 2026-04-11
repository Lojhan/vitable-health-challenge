from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Protocol


class DuplicateEmailError(ValueError):
    pass


@dataclass(frozen=True)
class SignUpUserCommand:
    email: str
    password: str
    first_name: str
    insurance_tier: str


@dataclass(frozen=True)
class SignUpUserResult:
    email: str
    first_name: str
    insurance_tier: str


@dataclass(frozen=True)
class UserSignedUpEvent:
    user_id: int
    email: str
    first_name: str
    insurance_tier: str

    @property
    def aggregate_type(self) -> str:
        return 'users.user'

    @property
    def aggregate_id(self) -> str:
        return str(self.user_id)

    @property
    def event_type(self) -> str:
        return 'users.user_signed_up'


class SignUpUserUnitOfWork(Protocol):
    def __enter__(self) -> SignUpUserUnitOfWork: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None: ...
    def email_exists(self, email: str) -> bool: ...
    def create_user(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        insurance_tier: str,
    ) -> object: ...
    def record_event(self, event: UserSignedUpEvent) -> None: ...
