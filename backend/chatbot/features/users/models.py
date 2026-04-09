from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
	INSURANCE_TIER_BRONZE = 'Bronze'
	INSURANCE_TIER_SILVER = 'Silver'
	INSURANCE_TIER_GOLD = 'Gold'
	INSURANCE_TIER_CHOICES = [
		(INSURANCE_TIER_BRONZE, INSURANCE_TIER_BRONZE),
		(INSURANCE_TIER_SILVER, INSURANCE_TIER_SILVER),
		(INSURANCE_TIER_GOLD, INSURANCE_TIER_GOLD),
	]

	insurance_tier = models.CharField(
		max_length=10,
		choices=INSURANCE_TIER_CHOICES,
		default=INSURANCE_TIER_BRONZE,
	)
	medical_history = models.JSONField(default=dict, blank=True)
