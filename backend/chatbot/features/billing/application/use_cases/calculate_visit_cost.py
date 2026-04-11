from chatbot.features.core.application.contracts import BaseUseCase
from chatbot.features.core.constants import InsuranceTier
from chatbot.features.core.domain.validation import require_insurance_tier, require_non_blank_text

VISIT_COST_BY_TIER = {
    InsuranceTier.BRONZE.value: 150.0,
    InsuranceTier.SILVER.value: 75.0,
    InsuranceTier.GOLD.value: 20.0,
}


class CalculateVisitCostUseCase(BaseUseCase):
    def execute(self, *, insurance_tier: str, visit_type: str) -> float:
        normalized_insurance_tier = require_insurance_tier(insurance_tier)
        _ = require_non_blank_text(visit_type, field='visit_type')
        try:
            return VISIT_COST_BY_TIER[normalized_insurance_tier]
        except KeyError as error:
            raise ValueError('Unknown insurance tier') from error
