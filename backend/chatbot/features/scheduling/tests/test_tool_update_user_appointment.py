from datetime import UTC, datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from chatbot.features.scheduling.models import Appointment, Provider
from chatbot.features.scheduling.tests.helpers import make_provider, pk
from chatbot.features.scheduling.tools import update_user_appointment


@pytest.mark.django_db
def test_update_user_appointment_only_updates_user_owned_record():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='update-user',
        password='safe-password-123',
        insurance_tier='Bronze',
        medical_history={},
    )
    other_user = user_model.objects.create_user(
        username='other-update-user',
        password='safe-password-123',
        insurance_tier='Bronze',
        medical_history={},
    )

    appointment = Appointment.objects.create(
        user=user,
        title='Own appointment',
        time_slot=timezone.make_aware(datetime.fromisoformat('2026-04-14T09:00:00')),
        rrule='FREQ=DAILY;COUNT=1',
    )
    original_version = appointment.version
    others_appointment = Appointment.objects.create(
        user=other_user,
        title='Other appointment',
        time_slot=timezone.make_aware(datetime.fromisoformat('2026-04-14T10:00:00')),
        rrule='FREQ=DAILY;COUNT=1',
    )

    updated = update_user_appointment(
        user_id=pk(user),
        appointment_id=pk(appointment),
        time_slot='2026-04-15T11:00:00',
        rrule_str='FREQ=WEEKLY;COUNT=2',
        symptoms_summary='High fever and body aches',
        appointment_reason='Rule out flu and dehydration risk',
    )
    denied = update_user_appointment(
        user_id=pk(user),
        appointment_id=pk(others_appointment),
        time_slot='2026-04-15T12:00:00',
    )

    appointment.refresh_from_db()
    others_appointment.refresh_from_db()

    assert updated == {
        'appointment_id': pk(appointment),
        'updated': True,
        'appointment': {
            'appointment_id': pk(appointment),
            'title': 'Own appointment',
            'time_slot': '2026-04-15T11:00:00',
            'time_slot_human_utc': 'Wednesday, April 15, 2026 at 11:00 AM UTC',
            'rrule': 'FREQ=WEEKLY;COUNT=2',
            'symptoms_summary': 'High fever and body aches',
            'appointment_reason': 'Rule out flu and dehydration risk',
            'provider_id': None,
            'provider_name': None,
        },
    }
    assert denied == {
        'appointment_id': pk(others_appointment),
        'updated': False,
        'reason': 'not_found',
    }
    assert appointment.time_slot.replace(tzinfo=None) == datetime.fromisoformat(
        '2026-04-15T11:00:00'
    )
    assert appointment.rrule == 'FREQ=WEEKLY;COUNT=2'
    assert appointment.version == original_version + 1
    assert others_appointment.time_slot.replace(tzinfo=None) == datetime.fromisoformat(
        '2026-04-14T10:00:00'
    )


@pytest.mark.django_db
def test_update_user_appointment_reassigns_provider_when_slot_is_valid():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='reassign-provider-user',
        password='safe-password-123',
        insurance_tier='Silver',
        medical_history={},
    )
    provider_a = make_provider('Dr. A', 'General')
    provider_b = make_provider('Dr. B', 'General')
    appointment = Appointment.objects.create(
        user=user,
        title='Booked',
        time_slot=datetime(2026, 4, 10, 9, 0, 0, tzinfo=UTC),
        rrule='FREQ=DAILY;COUNT=1',
        provider=provider_a,
    )

    result = update_user_appointment(
        user_id=pk(user),
        appointment_id=pk(appointment),
        provider_id=pk(provider_b),
    )

    assert result['updated'] is True
    appointment.refresh_from_db()
    assert appointment.provider_id == pk(provider_b)


@pytest.mark.django_db
def test_update_user_appointment_raises_when_new_slot_outside_new_provider_availability():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='update-outside-slot-user',
        password='safe-password-123',
        insurance_tier='Bronze',
        medical_history={},
    )
    provider_a = make_provider('Dr. A', 'General')
    provider_b = Provider.objects.create(
        name='Dr. B Afternoon',
        specialty='Cardiology',
        availability_dtstart=datetime(2026, 4, 10, 14, 0, 0, tzinfo=UTC),
        availability_rrule='FREQ=DAILY;BYHOUR=14,15;BYMINUTE=0;BYSECOND=0',
    )
    appointment = Appointment.objects.create(
        user=user,
        title='Booked',
        time_slot=datetime(2026, 4, 10, 9, 0, 0, tzinfo=UTC),
        rrule='FREQ=DAILY;COUNT=1',
        provider=provider_a,
    )

    with pytest.raises(ValueError, match='not within provider'):
        update_user_appointment(
            user_id=pk(user),
            appointment_id=pk(appointment),
            time_slot='2026-04-10T09:00:00',
            provider_id=pk(provider_b),
        )
