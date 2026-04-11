from typing import Any

from ninja import Router, Schema
from ninja.responses import Status
from pydantic import ValidationInfo, field_validator

from chatbot.features.core.api.validation import ValidationErrorResponseSchema, to_validation_status
from chatbot.features.core.constants import InsuranceTier
from chatbot.features.core.domain.validation import DomainValidationError, require_non_blank_text
from chatbot.features.users.application.signup import DuplicateEmailError, SignUpUserCommand
from chatbot.features.users.composition import build_signup_use_case

router = Router()


class SignupRequestSchema(Schema):
    email: str
    password: str
    first_name: str
    insurance_tier: InsuranceTier

    @field_validator('email', 'password', 'first_name')
    @classmethod
    def validate_required_text(
        cls: type['SignupRequestSchema'],
        value: str,
        info: ValidationInfo,
    ) -> str:
        return require_non_blank_text(value, field=info.field_name)


class SignupResponseSchema(Schema):
    email: str
    first_name: str
    insurance_tier: str


class SignupErrorSchema(Schema):
    detail: str


@router.post(
    '/signup',
    response={
        201: SignupResponseSchema,
        409: SignupErrorSchema,
        422: ValidationErrorResponseSchema,
    },
)
def signup(request: Any, payload: SignupRequestSchema) -> Status:
    _ = request
    use_case = build_signup_use_case()

    try:
        result = use_case.execute(
            SignUpUserCommand(
                email=payload.email,
                password=payload.password,
                first_name=payload.first_name,
                insurance_tier=str(payload.insurance_tier),
            )
        )
    except DuplicateEmailError as error:
        return Status(409, {'detail': str(error)})
    except DomainValidationError as error:
        return to_validation_status(error)

    return Status(201, SignupResponseSchema(
        email=result.email,
        first_name=result.first_name,
        insurance_tier=result.insurance_tier,
    ))
