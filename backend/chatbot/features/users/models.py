from django.contrib.auth.models import AbstractUser
from django.db import models

from chatbot.features.core.constants import INSURANCE_TIER_CHOICES, InsuranceTier


class User(AbstractUser):
	INSURANCE_TIER_BRONZE = InsuranceTier.BRONZE.value
	INSURANCE_TIER_SILVER = InsuranceTier.SILVER.value
	INSURANCE_TIER_GOLD = InsuranceTier.GOLD.value
	INSURANCE_TIER_CHOICES = INSURANCE_TIER_CHOICES

	insurance_tier = models.CharField(
		max_length=10,
		choices=INSURANCE_TIER_CHOICES,
		default=InsuranceTier.BRONZE.value,
	)
	medical_history = models.JSONField(default=dict, blank=True)

	class Meta:
		constraints = [
			models.CheckConstraint(
				condition=models.Q(
					insurance_tier__in=[
						InsuranceTier.BRONZE.value,
						InsuranceTier.SILVER.value,
						InsuranceTier.GOLD.value,
					]
				),
				name='users_insurance_tier_valid_choice',
			),
		]
