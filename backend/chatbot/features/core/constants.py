from enum import StrEnum


class InsuranceTier(StrEnum):
    BRONZE = 'Bronze'
    SILVER = 'Silver'
    GOLD = 'Gold'


INSURANCE_TIER_CHOICES = [(tier.value, tier.value) for tier in InsuranceTier]
