import pytest

from chatbot.features.billing.tools import VISIT_COST_BY_TIER, calculate_visit_cost
from chatbot.features.core.constants import InsuranceTier


@pytest.mark.parametrize(
    ('insurance_tier', 'visit_type', 'expected_cost'),
    [
        ('Bronze', 'urgent-care', 150.0),
        ('Silver', 'urgent-care', 75.0),
        ('Gold', 'urgent-care', 20.0),
    ],
)
def test_calculate_visit_cost_by_insurance_tier(
    insurance_tier: str,
    visit_type: str,
    expected_cost: float,
):
    assert calculate_visit_cost(insurance_tier, visit_type) == expected_cost


def test_calculate_visit_cost_rejects_unknown_tier():
    with pytest.raises(ValueError, match='insurance tier'):
        calculate_visit_cost('Platinum', 'urgent-care')


def test_visit_costs_cover_all_supported_insurance_tiers():
    assert set(VISIT_COST_BY_TIER) == {tier.value for tier in InsuranceTier}
