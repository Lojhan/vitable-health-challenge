from datetime import datetime
from datetime import timezone as dt_timezone
from typing import Any, cast
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from chatbot.features.scheduling.models import Appointment, Provider
from chatbot.features.scheduling.tools import (
    book_appointment,
    cancel_user_appointment,
    check_availability,
    list_providers,
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
            'provider_id': None,
            'provider_name': None,
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
def test_cancel_and_update_accept_loosely_formatted_appointment_ids():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='coerce-id-user',
        password='safe-password-123',
        insurance_tier='Silver',
        medical_history={},
    )

    appointment = Appointment.objects.create(
        user=user,
        title='Needs cancellation',
        time_slot=timezone.make_aware(datetime.fromisoformat('2026-04-18T10:00:00')),
        rrule='FREQ=DAILY;COUNT=1',
    )

    update_result = update_user_appointment(
        user_id=_pk(user),
        appointment_id=f'Appointment #{_pk(appointment)}:',
        time_slot='2026-04-18T11:00:00',
    )
    assert update_result['updated'] is True

    cancel_result = cancel_user_appointment(
        user_id=_pk(user),
        appointment_id=f'#{_pk(appointment)}',
    )
    assert cancel_result == {'appointment_id': _pk(appointment), 'cancelled': True}
    assert Appointment.objects.filter(id=_pk(appointment)).exists() is False


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
            'provider_id': None,
            'provider_name': None,
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


@pytest.mark.django_db
def test_book_appointment_with_appointment_id_moves_existing_without_duplicates():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='reschedule-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )

    existing = Appointment.objects.create(
        user=user,
        title='Booked Appointment',
        time_slot=timezone.make_aware(datetime.fromisoformat('2026-04-20T09:00:00')),
        rrule='FREQ=DAILY;COUNT=1',
        symptoms_summary='Sore throat',
        appointment_reason='Initial consult',
    )

    moved = book_appointment(
        user_id=_pk(user),
        appointment_id=_pk(existing),
        time_slot='2026-04-22T14:00:00',
        rrule_str='FREQ=DAILY;COUNT=1',
        symptoms_summary='Sore throat',
        appointment_reason='Initial consult',
    )

    assert _pk(moved) == _pk(existing)
    assert Appointment.objects.filter(user_id=_pk(user)).count() == 1
    moved.refresh_from_db()
    assert moved.time_slot.replace(tzinfo=None) == datetime.fromisoformat('2026-04-22T14:00:00')


def test_resolve_datetime_reference_next_monday_uses_next_week_anchor():
    frozen_now = timezone.make_aware(datetime.fromisoformat('2026-04-06T08:00:00'))

    with patch('chatbot.features.scheduling.tools.timezone.now', return_value=frozen_now):
        resolved = resolve_datetime_reference('next monday')

    assert resolved.get('resolved') is True
    assert resolved.get('iso_datetime_utc') == '2026-04-13T09:00:00'


# ── Provider / list_providers ──────────────────────────────────────────────────


def _make_provider(name: str = 'Dr. Alice Smith', specialty: str = 'General Practice') -> Provider:
    return Provider.objects.create(
        name=name,
        specialty=specialty,
        availability_dtstart=datetime(2026, 4, 10, 9, 0, 0, tzinfo=dt_timezone.utc),
        availability_rrule='FREQ=DAILY;BYHOUR=9,10,11;BYMINUTE=0;BYSECOND=0',
    )


# T1
@pytest.mark.django_db
def test_list_providers_returns_all_seeded_providers():
    # The seed migration already inserted 5 providers. We add 2 more and verify
    # both new ones appear in the result alongside the seeded ones.
    _make_provider('Dr. Alice Smith', 'General Practice')
    _make_provider('Dr. Bob Jones', 'Cardiology')

    result = list_providers()

    names = {p['name'] for p in result}
    assert 'Dr. Alice Smith' in names
    assert 'Dr. Bob Jones' in names
    for p in result:
        assert 'provider_id' in p
        assert 'specialty' in p


# T2
@pytest.mark.django_db
def test_list_providers_returns_empty_when_no_providers_exist():
    # Delete all providers (including seeded ones) and verify empty result.
    Provider.objects.all().delete()
    assert list_providers() == []


# ── check_availability — provider-aware ──────────────────────────────────────


# T3
@pytest.mark.django_db
def test_check_availability_with_provider_id_returns_only_provider_rrule_slots():
    provider = _make_provider()

    slots = check_availability(
        '2026-04-10T08:00:00/2026-04-10T13:00:00',
        provider_id=provider.pk,
    )

    assert '2026-04-10T08:00:00' not in slots
    assert '2026-04-10T09:00:00' in slots
    assert '2026-04-10T10:00:00' in slots
    assert '2026-04-10T11:00:00' in slots
    assert '2026-04-10T12:00:00' not in slots


# T4
@pytest.mark.django_db
def test_check_availability_excludes_already_booked_provider_slots():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='provider-avail-booked-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )
    provider = _make_provider()
    Appointment.objects.create(
        user=user,
        title='Booked',
        time_slot=datetime(2026, 4, 10, 9, 0, 0, tzinfo=dt_timezone.utc),
        rrule='FREQ=DAILY;COUNT=1',
        provider=provider,
    )

    slots = check_availability(
        '2026-04-10T09:00:00/2026-04-10T12:00:00',
        provider_id=provider.pk,
    )

    assert '2026-04-10T09:00:00' not in slots
    assert '2026-04-10T10:00:00' in slots
    assert '2026-04-10T11:00:00' in slots


# T5
@pytest.mark.django_db
def test_check_availability_provider_a_booking_does_not_block_provider_b():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='two-provider-avail-user',
        password='safe-password-123',
        insurance_tier='Silver',
        medical_history={},
    )
    provider_a = _make_provider('Dr. A', 'General')
    provider_b = _make_provider('Dr. B', 'General')
    Appointment.objects.create(
        user=user,
        title='Booked with A',
        time_slot=datetime(2026, 4, 10, 9, 0, 0, tzinfo=dt_timezone.utc),
        rrule='FREQ=DAILY;COUNT=1',
        provider=provider_a,
    )

    slots_b = check_availability(
        '2026-04-10T09:00:00/2026-04-10T11:00:00',
        provider_id=provider_b.pk,
    )

    assert '2026-04-10T09:00:00' in slots_b


# T6
@pytest.mark.django_db
def test_check_availability_returns_empty_when_provider_has_no_occurrences_in_range():
    provider = Provider.objects.create(
        name='Dr. Future',
        specialty='Neurology',
        availability_dtstart=datetime(2026, 5, 1, 9, 0, 0, tzinfo=dt_timezone.utc),
        availability_rrule='FREQ=WEEKLY;BYDAY=FR;BYHOUR=9;BYMINUTE=0;BYSECOND=0',
    )

    slots = check_availability(
        '2026-04-10T09:00:00/2026-04-10T12:00:00',
        provider_id=provider.pk,
    )

    assert slots == []


# T7
@pytest.mark.django_db
def test_check_availability_without_provider_id_preserves_open_agenda_behavior():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='open-agenda-compat-user',
        password='safe-password-123',
        insurance_tier='Silver',
        medical_history={},
    )
    Appointment.objects.create(
        user=user,
        title='Existing',
        time_slot=timezone.make_aware(datetime.fromisoformat('2026-04-10T10:00:00')),
        rrule='FREQ=DAILY;COUNT=1',
    )

    slots = check_availability('2026-04-10T09:00:00/2026-04-10T12:00:00')

    assert '2026-04-10T09:00:00' in slots
    assert '2026-04-10T10:00:00' not in slots
    assert '2026-04-10T11:00:00' in slots


# ── book_appointment — provider-aware ─────────────────────────────────────────


# T8
@pytest.mark.django_db
def test_book_appointment_with_provider_id_persists_foreign_key():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='provider-book-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )
    provider = _make_provider()

    appointment = book_appointment(
        user_id=_pk(user),
        time_slot='2026-04-10T09:00:00',
        symptoms_summary='Sore throat',
        appointment_reason='Initial consult',
        provider_id=_pk(provider),
    )

    appointment.refresh_from_db()
    assert appointment.provider_id == _pk(provider)


# T9
@pytest.mark.django_db
def test_book_appointment_raises_when_slot_outside_provider_availability():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='outside-slot-user',
        password='safe-password-123',
        insurance_tier='Bronze',
        medical_history={},
    )
    provider = _make_provider()

    with pytest.raises(ValueError, match='not within provider'):
        book_appointment(
            user_id=_pk(user),
            time_slot='2026-04-10T08:00:00',
            symptoms_summary='Sore throat',
            appointment_reason='Initial consult',
            provider_id=_pk(provider),
        )


# T10
@pytest.mark.django_db
def test_book_appointment_raises_on_double_booking_same_provider_and_slot():
    user_model = get_user_model()
    user_a = user_model.objects.create_user(
        username='double-book-user-a',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )
    user_b = user_model.objects.create_user(
        username='double-book-user-b',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )
    provider = _make_provider()

    book_appointment(
        user_id=_pk(user_a),
        time_slot='2026-04-10T09:00:00',
        symptoms_summary='Fever',
        appointment_reason='Checkup',
        provider_id=_pk(provider),
    )

    with pytest.raises(ValueError, match='already booked'):
        book_appointment(
            user_id=_pk(user_b),
            time_slot='2026-04-10T09:00:00',
            symptoms_summary='Cough',
            appointment_reason='Checkup',
            provider_id=_pk(provider),
        )


# T11
@pytest.mark.django_db
def test_book_appointment_without_provider_id_still_works():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='no-provider-book-user',
        password='safe-password-123',
        insurance_tier='Silver',
        medical_history={},
    )

    appointment = book_appointment(
        user_id=_pk(user),
        time_slot='2026-04-12T09:00:00',
        symptoms_summary='Headache',
        appointment_reason='Assessment',
    )

    assert appointment.provider_id is None


# T12
@pytest.mark.django_db
def test_book_appointment_reschedule_with_appointment_id_changes_provider():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='reschedule-provider-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )
    provider_a = _make_provider('Dr. A', 'General')
    provider_b = _make_provider('Dr. B', 'General')

    appointment = book_appointment(
        user_id=_pk(user),
        time_slot='2026-04-10T09:00:00',
        symptoms_summary='Fever',
        appointment_reason='Checkup',
        provider_id=_pk(provider_a),
    )

    rescheduled = book_appointment(
        user_id=_pk(user),
        appointment_id=_pk(appointment),
        time_slot='2026-04-10T10:00:00',
        symptoms_summary='Fever',
        appointment_reason='Checkup',
        provider_id=_pk(provider_b),
    )

    assert _pk(rescheduled) == _pk(appointment)
    rescheduled.refresh_from_db()
    assert rescheduled.provider_id == _pk(provider_b)
    assert Appointment.objects.filter(user_id=_pk(user)).count() == 1


# ── list_user_appointments — provider serialization ───────────────────────────


# T13
@pytest.mark.django_db
def test_list_user_appointments_serializes_provider_info_when_set():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='serialize-provider-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )
    provider = _make_provider()
    Appointment.objects.create(
        user=user,
        title='Booked Appointment',
        time_slot=datetime(2026, 4, 12, 9, 0, 0, tzinfo=dt_timezone.utc),
        rrule='FREQ=DAILY;COUNT=1',
        provider=provider,
    )

    result = list_user_appointments(user_id=_pk(user))

    assert result['count'] == 1
    serialized = result['appointments'][0]
    assert serialized['provider_id'] == _pk(provider)
    assert serialized['provider_name'] == 'Dr. Alice Smith'


# T14
@pytest.mark.django_db
def test_list_user_appointments_serializes_null_provider_when_unset():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='no-provider-serialize-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )
    Appointment.objects.create(
        user=user,
        title='Open Agenda',
        time_slot=datetime(2026, 4, 12, 10, 0, 0, tzinfo=dt_timezone.utc),
        rrule='FREQ=DAILY;COUNT=1',
    )

    result = list_user_appointments(user_id=_pk(user))

    assert result['count'] == 1
    serialized = result['appointments'][0]
    assert serialized['provider_id'] is None
    assert serialized['provider_name'] is None


# ── update_user_appointment — provider-aware ──────────────────────────────────


# T15
@pytest.mark.django_db
def test_update_user_appointment_reassigns_provider_when_slot_is_valid():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='reassign-provider-user',
        password='safe-password-123',
        insurance_tier='Silver',
        medical_history={},
    )
    provider_a = _make_provider('Dr. A', 'General')
    provider_b = _make_provider('Dr. B', 'General')
    appointment = Appointment.objects.create(
        user=user,
        title='Booked',
        time_slot=datetime(2026, 4, 10, 9, 0, 0, tzinfo=dt_timezone.utc),
        rrule='FREQ=DAILY;COUNT=1',
        provider=provider_a,
    )

    result = update_user_appointment(
        user_id=_pk(user),
        appointment_id=_pk(appointment),
        provider_id=_pk(provider_b),
    )

    assert result['updated'] is True
    appointment.refresh_from_db()
    assert appointment.provider_id == _pk(provider_b)


# T16
@pytest.mark.django_db
def test_update_user_appointment_raises_when_new_slot_outside_new_provider_availability():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='update-outside-slot-user',
        password='safe-password-123',
        insurance_tier='Bronze',
        medical_history={},
    )
    provider_a = _make_provider('Dr. A', 'General')
    provider_b = Provider.objects.create(
        name='Dr. B Afternoon',
        specialty='Cardiology',
        availability_dtstart=datetime(2026, 4, 10, 14, 0, 0, tzinfo=dt_timezone.utc),
        availability_rrule='FREQ=DAILY;BYHOUR=14,15;BYMINUTE=0;BYSECOND=0',
    )
    appointment = Appointment.objects.create(
        user=user,
        title='Booked',
        time_slot=datetime(2026, 4, 10, 9, 0, 0, tzinfo=dt_timezone.utc),
        rrule='FREQ=DAILY;COUNT=1',
        provider=provider_a,
    )

    with pytest.raises(ValueError, match='not within provider'):
        update_user_appointment(
            user_id=_pk(user),
            appointment_id=_pk(appointment),
            time_slot='2026-04-10T09:00:00',
            provider_id=_pk(provider_b),
        )
