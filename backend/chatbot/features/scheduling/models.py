from django.conf import settings
from django.db import models
from django.utils import timezone


class Provider(models.Model):
    name = models.CharField(max_length=200)
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

	class Meta:
		indexes = [
			models.Index(fields=['user_id', 'time_slot']),
			models.Index(fields=['provider_id', 'time_slot']),
		]

	def __str__(self):
		return f'{self.title} ({self.user_id})'
