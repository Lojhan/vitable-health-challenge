from __future__ import annotations

import re
from dataclasses import dataclass

from chatbot.features.core.constants import InsuranceTier


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    code: str
    detail: str


class DomainValidationError(ValueError):
    def __init__(self, issues: list[ValidationIssue]) -> None:
        if not issues:
            issues = [ValidationIssue(field='unknown', code='invalid', detail='Invalid input')]
        self.issues = issues
        super().__init__(issues[0].detail)

    @property
    def detail(self) -> str:
        return self.issues[0].detail

    def to_payload(self) -> dict[str, object]:
        return {
            'detail': self.detail,
            'errors': [
                {
                    'field': issue.field,
                    'code': issue.code,
                    'detail': issue.detail,
                }
                for issue in self.issues
            ],
        }


_EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def require_non_blank_text(value: str, *, field: str) -> str:
    normalized = value.strip()
    if normalized:
        return normalized
    raise DomainValidationError(
        [
            ValidationIssue(
                field=field,
                code='blank',
                detail=f'{field} cannot be blank',
            )
        ]
    )


def require_email(value: str, *, field: str = 'email') -> str:
    normalized = require_non_blank_text(value, field=field).lower()
    if _EMAIL_PATTERN.fullmatch(normalized):
        return normalized

    raise DomainValidationError(
        [
            ValidationIssue(
                field=field,
                code='invalid_format',
                detail=f'{field} must be a valid email address',
            )
        ]
    )


def require_insurance_tier(value: str, *, field: str = 'insurance_tier') -> str:
    try:
        return InsuranceTier(value).value
    except ValueError as error:
        allowed = ', '.join(tier.value for tier in InsuranceTier)
        field_label = field.replace('_', ' ')
        raise DomainValidationError(
            [
                ValidationIssue(
                    field=field,
                    code='invalid_choice',
                    detail=f'{field_label} must be one of: {allowed}',
                )
            ]
        ) from error


def require_positive_int(value: int, *, field: str) -> int:
    if value > 0:
        return value
    raise DomainValidationError(
        [
            ValidationIssue(
                field=field,
                code='invalid_value',
                detail=f'{field} must be a positive integer',
            )
        ]
    )


def require_non_negative_float(value: float, *, field: str) -> float:
    if value >= 0:
        return value
    raise DomainValidationError(
        [
            ValidationIssue(
                field=field,
                code='invalid_value',
                detail=f'{field} must be a non-negative number',
            )
        ]
    )
