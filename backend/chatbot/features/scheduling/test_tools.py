from datetime import datetime
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from chatbot.features.scheduling.models import Appointment
from chatbot.features.scheduling.tools import (
    book_appointment,
    cancel_user_appointment,
    check_availability,
    list_user_appointments,
    resolve_datetime_reference,
    update_user_appointment,
)


def _pk(instance: object) -> int:
    return cast(int, cast(Any, instance).pk)


def _user_id(appointment: Appointment) -> int:
    return cast(int, cast(Any, appointment).user_id)


@pytest.mark.django_db
def test_check_availability_avoids_conflicts_from_rrule():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='schedule-user',
        password='safe-password-123',
        insurance_tier='Silver',
        medical_history={},
    )

    Appointment.objects.create(
        user=user,
        title='Existing Appointment',
        time_slot=timezone.make_aware(datetime.fromisoformat('2026-04-10T10:00:00')),
        rrule='FREQ=DAILY;COUNT=1',
    )

    available_slots = check_availability('2026-04-10T09:00:00/2026-04-10T12:00:00')

    assert '2026-04-10T09:00:00' in available_slots
    assert '2026-04-10T10:00:00' not in available_slots
    assert '2026-04-10T11:00:00' in available_slots


@pytest.mark.django_db
def test_check_availability_accepts_single_datetime_and_builds_multi_slot_window():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='single-datetime-user',
        password='safe-password-123',
        insurance_tier='Silver',
        medical_history={},
    )

    Appointment.objects.create(
        user=user,
        title='Existing Appointment',
        time_slot=timezone.make_aware(datetime.fromisoformat('2026-04-10T10:00:00')),
        rrule='FREQ=DAILY;COUNT=1',
    )

    available_slots = check_availability('2026-04-10T09:00:00')

    assert '2026-04-10T09:00:00' in available_slots
    assert '2026-04-10T10:00:00' not in available_slots
    assert '2026-04-10T16:00:00' in available_slots


@pytest.mark.django_db
def test_check_availability_accepts_single_date_and_uses_business_hours_window():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='single-date-user',
        password='safe-password-123',
        insurance_tier='Silver',
        medical_history={},
    )

    Appointment.objects.create(
        user=user,
        title='Existing Appointment',
        time_slot=timezone.make_aware(datetime.fromisoformat('2026-04-10T10:00:00')),
        rrule='FREQ=DAILY;COUNT=1',
    )

    available_slots = check_availability('2026-04-10')

    assert '2026-04-10T09:00:00' in available_slots
    assert '2026-04-10T10:00:00' not in available_slots
    assert '2026-04-10T16:00:00' in available_slots


@pytest.mark.django_db
def test_book_appointment_creates_appointment_with_optional_rrule():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='book-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )

    appointment = book_appointment(
        user_id=_pk(user),
        time_slot='2026-04-11T09:30:00',
        rrule_str='FREQ=WEEKLY;BYDAY=MO;COUNT=4',
        symptoms_summary='Persistent dry cough for 4 days',
        appointment_reason='Needs clinician assessment for worsening cough',
    )

    assert _user_id(appointment) == _pk(user)
    assert appointment.time_slot.replace(tzinfo=None) == datetime.fromisoformat(
        '2026-04-11T09:30:00'
    )
    assert appointment.rrule == 'FREQ=WEEKLY;BYDAY=MO;COUNT=4'
    assert appointment.symptoms_summary == 'Persistent dry cough for 4 days'
    assert (
        appointment.appointment_reason
        == 'Needs clinician assessment for worsening cough'
    )


def test_resolve_datetime_reference_handles_tomorrow_with_time():
    resolved = resolve_datetime_reference('tomorrow at 9:30 am')

    assert resolved.get('resolved') is True
    iso_datetime_utc = resolved.get('iso_datetime_utc')
    assert iso_datetime_utc is not None
    assert iso_datetime_utc.endswith('09:30:00')


@pytest.mark.django_db
def test_list_user_appointments_returns_empty_formatted_payload_when_none_exist():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='empty-list-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )

    appointments = list_user_appointments(user_id=_pk(user))

    assert appointments['count'] == 0
    assert appointments['appointments'] == []
    assert appointments['formatted_lines'] == []
    assert appointments['summary'] == 'You have no upcoming appointments.'


@pytest.mark.django_db
def test_list_user_appointments_returns_only_user_appointments():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='list-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )
    other_user = user_model.objects.create_user(
        username='other-list-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )

    first = Appointment.objects.create(
        user=user,
        title='First',
        time_slot=timezone.make_aware(datetime.fromisoformat('2026-04-12T09:00:00')),
        rrule='FREQ=DAILY;COUNT=1',
    )
    Appointment.objects.create(
        user=other_user,
        title='Other',
        time_slot=timezone.make_aware(datetime.fromisoformat('2026-04-12T10:00:00')),
        rrule='FREQ=DAILY;COUNT=1',
    )

    appointments = list_user_appointments(user_id=_pk(user))

    assert appointments['count'] == 1
    assert appointments['summary'] == 'You have 1 upcoming appointment(s).'
    assert appointments['appointments'] == [
        {
            'appointment_id': _pk(first),
            'title': 'First',
            'time_slot': '2026-04-12T09:00:00',
            'time_slot_human_utc': 'Sunday, April 12, 2026 at 09:00 AM UTC',
            'rrule': 'FREQ=DAILY;COUNT=1',
            'symptoms_summary': '',
            'appointment_reason': '',
        }
    ]
    assert len(appointments['formatted_lines']) == 1
    assert 'Appointment #' in appointments['formatted_lines'][0]


@pytest.mark.django_db
def test_cancel_user_appointment_only_cancels_user_owned_records():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='cancel-user',
        password='safe-password-123',
        insurance_tier='Silver',
        medical_history={},
    )
    other_user = user_model.objects.create_user(
        username='other-cancel-user',
        password='safe-password-123',
        insurance_tier='Silver',
        medical_history={},
    )

    own_appointment = Appointment.objects.create(
        user=user,
        title='Own appointment',
        time_slot=timezone.make_aware(datetime.fromisoformat('2026-04-13T09:00:00')),
        rrule='FREQ=DAILY;COUNT=1',
    )
    others_appointment = Appointment.objects.create(
        user=other_user,
        title='Other appointment',
        time_slot=timezone.make_aware(datetime.fromisoformat('2026-04-13T10:00:00')),
        rrule='FREQ=DAILY;COUNT=1',
    )

    cancelled = cancel_user_appointment(user_id=_pk(user), appointment_id=_pk(own_appointment))
    denied = cancel_user_appointment(user_id=_pk(user), appointment_id=_pk(others_appointment))

    assert cancelled == {'appointment_id': _pk(own_appointment), 'cancelled': True}
    assert denied == {'appointment_id': _pk(others_appointment), 'cancelled': False}
    assert Appointment.objects.filter(id=_pk(own_appointment)).exists() is False
    assert Appointment.objects.filter(id=_pk(others_appointment)).exists() is True


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
    others_appointment = Appointment.objects.create(
        user=other_user,
        title='Other appointment',
        time_slot=timezone.make_aware(datetime.fromisoformat('2026-04-14T10:00:00')),
        rrule='FREQ=DAILY;COUNT=1',
    )

    updated = update_user_appointment(
        user_id=_pk(user),
        appointment_id=_pk(appointment),
        time_slot='2026-04-15T11:00:00',
        rrule_str='FREQ=WEEKLY;COUNT=2',
        symptoms_summary='High fever and body aches',
        appointment_reason='Rule out flu and dehydration risk',
    )
    denied = update_user_appointment(
        user_id=_pk(user),
        appointment_id=_pk(others_appointment),
        time_slot='2026-04-15T12:00:00',
    )

    appointment.refresh_from_db()
    others_appointment.refresh_from_db()

    assert updated == {
        'appointment_id': _pk(appointment),
        'updated': True,
        'appointment': {
            'appointment_id': _pk(appointment),
            'title': 'Own appointment',
            'time_slot': '2026-04-15T11:00:00',
            'time_slot_human_utc': 'Wednesday, April 15, 2026 at 11:00 AM UTC',
            'rrule': 'FREQ=WEEKLY;COUNT=2',
            'symptoms_summary': 'High fever and body aches',
            'appointment_reason': 'Rule out flu and dehydration risk',
        },
    }
    assert denied == {
        'appointment_id': _pk(others_appointment),
        'updated': False,
        'reason': 'not_found',
    }
    assert appointment.time_slot.replace(tzinfo=None) == datetime.fromisoformat(
        '2026-04-15T11:00:00'
    )
    assert appointment.rrule == 'FREQ=WEEKLY;COUNT=2'
    assert others_appointment.time_slot.replace(tzinfo=None) == datetime.fromisoformat(
        '2026-04-14T10:00:00'
    )
