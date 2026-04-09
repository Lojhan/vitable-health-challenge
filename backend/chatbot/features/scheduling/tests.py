import pytest
from django.contrib.auth import get_user_model

from chatbot.features.scheduling.models import Appointment


@pytest.mark.django_db
def test_appointment_stores_standard_rrule_string():
	user_model = get_user_model()
	user = user_model.objects.create_user(
		username='sam.patient',
		password='safe-password-123',
		insurance_tier='Silver',
		medical_history={'conditions': []},
	)

	appointment = Appointment.objects.create(
		user=user,
		title='Follow-up Consultation',
		rrule='FREQ=WEEKLY;BYDAY=MO;COUNT=6',
	)

	assert appointment.rrule == 'FREQ=WEEKLY;BYDAY=MO;COUNT=6'


def test_appointment_model_has_rrule_field():
	rrule_field = Appointment._meta.get_field('rrule')

	assert rrule_field.max_length == 255
	assert rrule_field.null is False
	assert rrule_field.blank is False
