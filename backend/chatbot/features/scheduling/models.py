from django.conf import settings
from django.db import models
from django.utils import timezone


class Provider(models.Model):
	name = models.CharField(max_length=200, unique=True)
	specialty = models.CharField(max_length=200)
	availability_dtstart = models.DateTimeField()
	availability_rrule = models.TextField()

	def __str__(self) -> str:
		return f'{self.name} ({self.specialty})'


class Appointment(models.Model):
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='appointments',
	)
	provider = models.ForeignKey(
		Provider,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='appointments',
	)
	title = models.CharField(max_length=255)
	time_slot = models.DateTimeField(default=timezone.now)
	rrule = models.CharField(max_length=255)
	symptoms_summary = models.TextField(default='')
	appointment_reason = models.TextField(default='')
	version = models.PositiveIntegerField(default=0)

	class Meta:
		indexes = [
			models.Index(fields=['user_id', 'time_slot']),
			models.Index(fields=['provider_id', 'time_slot']),
		]
		constraints = [
			models.CheckConstraint(
				condition=~models.Q(title__regex=r'^\s*$'),
				name='appointment_title_not_blank',
			),
			models.CheckConstraint(
				condition=~models.Q(rrule__regex=r'^\s*$'),
				name='appointment_rrule_not_blank',
			),
			models.UniqueConstraint(
				fields=['provider', 'time_slot'],
				condition=~models.Q(provider__isnull=True),
				name='appointment_provider_timeslot_unique',
			),
		]

	def __str__(self) -> str:
		return f'{self.title} ({self.user_id})'
