from ninja import Schema
from ninja.responses import Status

from chatbot.features.core.domain.validation import DomainValidationError


class ValidationIssueSchema(Schema):
    field: str
    code: str
    detail: str


class ValidationErrorResponseSchema(Schema):
    detail: str
    errors: list[ValidationIssueSchema]


def to_validation_status(error: DomainValidationError) -> Status:
    return Status(422, error.to_payload())
