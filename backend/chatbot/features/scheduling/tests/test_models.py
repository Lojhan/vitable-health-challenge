from datetime import UTC, datetime

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError
from django.utils import timezone

from chatbot.features.scheduling.infrastructure.provider_seed_data import PROVIDER_SEED_DATA
from chatbot.features.scheduling.infrastructure.time_context import build_temporal_anchor_lines
from chatbot.features.scheduling.models import Appointment, Provider
from chatbot.features.scheduling.tests.helpers import make_provider


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


@pytest.mark.django_db
def test_seed_providers_management_command_is_idempotent():
	Provider.objects.all().delete()

	call_command('seed_providers')
	assert Provider.objects.count() == len(PROVIDER_SEED_DATA)

	call_command('seed_providers')
	assert Provider.objects.count() == len(PROVIDER_SEED_DATA)


@pytest.mark.django_db
def test_provider_name_must_be_unique():
	Provider.objects.create(
		name='Dr. Unique Name',
		specialty='General Practice',
		availability_dtstart=timezone.now(),
		availability_rrule='FREQ=DAILY;COUNT=1',
	)

	with pytest.raises(IntegrityError):
		Provider.objects.create(
			name='Dr. Unique Name',
			specialty='Internal Medicine',
			availability_dtstart=timezone.now(),
			availability_rrule='FREQ=DAILY;COUNT=1',
		)


def test_build_temporal_anchor_lines_is_deterministic_for_given_now():
	now_utc = datetime(2026, 4, 10, 15, 45, 0, tzinfo=UTC)
	anchor_lines = build_temporal_anchor_lines(now_utc)

	assert 'today: 2026-04-10T00:00:00+00:00' in anchor_lines
	assert 'tomorrow: 2026-04-11T00:00:00+00:00' in anchor_lines
	assert 'in two weeks: 2026-04-24T00:00:00+00:00' in anchor_lines


@pytest.mark.django_db
def test_appointment_title_must_be_non_blank():
	user_model = get_user_model()
	user = user_model.objects.create_user(
		username='blank-title-user',
		password='safe-password-123',
		insurance_tier='Silver',
		medical_history={},
	)

	with pytest.raises(IntegrityError):
		Appointment.objects.create(
			user=user,
			title='   ',
			time_slot=timezone.now(),
			rrule='FREQ=DAILY;COUNT=1',
		)


@pytest.mark.django_db
def test_provider_cannot_have_two_appointments_at_same_time_slot():
	user_model = get_user_model()
	user_a = user_model.objects.create_user(
		username='provider-unique-user-a',
		password='safe-password-123',
		insurance_tier='Silver',
		medical_history={},
	)
	user_b = user_model.objects.create_user(
		username='provider-unique-user-b',
		password='safe-password-123',
		insurance_tier='Silver',
		medical_history={},
	)
	provider = make_provider('Dr. Persist', 'General')
	time_slot = datetime(2026, 4, 10, 9, 0, 0, tzinfo=UTC)

	Appointment.objects.create(
		user=user_a,
		title='A',
		time_slot=time_slot,
		rrule='FREQ=DAILY;COUNT=1',
		provider=provider,
	)

	with pytest.raises(IntegrityError):
		Appointment.objects.create(
			user=user_b,
			title='B',
			time_slot=time_slot,
			rrule='FREQ=DAILY;COUNT=1',
			provider=provider,
		)
