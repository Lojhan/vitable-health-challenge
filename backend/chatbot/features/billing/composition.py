from chatbot.features.billing.application.use_cases.calculate_visit_cost import (
    CalculateVisitCostUseCase,
)


def build_calculate_visit_cost_use_case() -> CalculateVisitCostUseCase:
    return CalculateVisitCostUseCase()
