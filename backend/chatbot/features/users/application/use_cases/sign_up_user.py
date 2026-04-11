from typing import Any, cast

from chatbot.features.core.application.contracts import BaseUseCase
from chatbot.features.core.domain.validation import (
    require_email,
    require_insurance_tier,
    require_non_blank_text,
)
from chatbot.features.users.application.signup import (
    DuplicateEmailError,
    SignUpUserCommand,
    SignUpUserResult,
    SignUpUserUnitOfWork,
    UserSignedUpEvent,
)


class SignUpUserUseCase(BaseUseCase):
    def __init__(self, uow: SignUpUserUnitOfWork) -> None:
        self._uow = uow

    def execute(self, command: SignUpUserCommand) -> SignUpUserResult:
        email = require_email(command.email)
        password = require_non_blank_text(command.password, field='password')
        first_name = require_non_blank_text(command.first_name, field='first_name')
        insurance_tier = require_insurance_tier(command.insurance_tier)

        with self._uow as uow:
            if uow.email_exists(email):
                raise DuplicateEmailError('A user with that email already exists.')

            user = uow.create_user(
                email=email,
                password=password,
                first_name=first_name,
                insurance_tier=insurance_tier,
            )
            typed_user = cast(Any, user)

            uow.record_event(
                UserSignedUpEvent(
                    user_id=int(typed_user.id),
                    email=typed_user.email,
                    first_name=typed_user.first_name,
                    insurance_tier=typed_user.insurance_tier,
                )
            )

            return SignUpUserResult(
                email=typed_user.email,
                first_name=typed_user.first_name,
                insurance_tier=typed_user.insurance_tier,
            )
