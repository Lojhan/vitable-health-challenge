from django.conf import settings
from django.db import models
from django.utils import timezone


class Appointment(models.Model):
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='appointments',
	)
	title = models.CharField(max_length=255)
	time_slot = models.DateTimeField(default=timezone.now)
	rrule = models.CharField(max_length=255)
	symptoms_summary = models.TextField(default='')
	appointment_reason = models.TextField(default='')

	def __str__(self):
		return f'{self.title} ({self.user_id})'
