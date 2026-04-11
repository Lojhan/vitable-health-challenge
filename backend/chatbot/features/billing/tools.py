from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator

from chatbot.features.ai.tooling import ToolContract
from chatbot.features.billing.application.use_cases.calculate_visit_cost import (
    VISIT_COST_BY_TIER,
)
from chatbot.features.billing.composition import build_calculate_visit_cost_use_case
from chatbot.features.core.constants import InsuranceTier


def _strip_and_require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f'{field_name} cannot be blank')
    return normalized


class CalculateVisitCostInputSchema(BaseModel):
    insurance_tier: InsuranceTier
    visit_type: str

    @field_validator('visit_type')
    @classmethod
    def validate_visit_type(cls: type[CalculateVisitCostInputSchema], value: str) -> str:
        return _strip_and_require_text(value, 'visit_type')


def calculate_visit_cost(insurance_tier: str, visit_type: str) -> float:
    return build_calculate_visit_cost_use_case().execute(
        insurance_tier=insurance_tier,
        visit_type=visit_type,
    )


def _execute_calculate_visit_cost(arguments: dict[str, Any], _user_id: int | None) -> object:
    return calculate_visit_cost(
        insurance_tier=arguments['insurance_tier'],
        visit_type=arguments['visit_type'],
    )


BILLING_TOOL_CONTRACTS = [
    ToolContract(
        name='calculate_visit_cost',
        description='Calculate a visit cost based on insurance tier and visit type.',
        input_schema=CalculateVisitCostInputSchema,
        executor=_execute_calculate_visit_cost,
    ),
]


__all__ = [
    'BILLING_TOOL_CONTRACTS',
    'VISIT_COST_BY_TIER',
    'calculate_visit_cost',
]
