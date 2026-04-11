from datetime import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from chatbot.features.scheduling.models import Appointment
from chatbot.features.scheduling.tests.helpers import make_provider, pk, user_id
from chatbot.features.scheduling.tools import book_appointment


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
        user_id=pk(user),
        time_slot='2026-04-11T09:30:00',
        rrule_str='FREQ=WEEKLY;BYDAY=MO;COUNT=4',
        symptoms_summary='Persistent dry cough for 4 days',
        appointment_reason='Needs clinician assessment for worsening cough',
    )

    assert user_id(appointment) == pk(user)
    assert appointment.time_slot.replace(tzinfo=None) == datetime.fromisoformat(
        '2026-04-11T09:30:00'
    )
    assert appointment.rrule == 'FREQ=WEEKLY;BYDAY=MO;COUNT=4'
    assert appointment.symptoms_summary == 'Persistent dry cough for 4 days'
    assert (
        appointment.appointment_reason
        == 'Needs clinician assessment for worsening cough'
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
        user_id=pk(user),
        appointment_id=pk(existing),
        time_slot='2026-04-22T14:00:00',
        rrule_str='FREQ=DAILY;COUNT=1',
        symptoms_summary='Sore throat',
        appointment_reason='Initial consult',
    )

    assert pk(moved) == pk(existing)
    assert Appointment.objects.filter(user_id=pk(user)).count() == 1
    moved.refresh_from_db()
    assert moved.time_slot.replace(tzinfo=None) == datetime.fromisoformat('2026-04-22T14:00:00')


@pytest.mark.django_db
def test_book_appointment_with_provider_id_persists_foreign_key():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='provider-book-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )
    provider = make_provider()

    appointment = book_appointment(
        user_id=pk(user),
        time_slot='2026-04-10T09:00:00',
        symptoms_summary='Sore throat',
        appointment_reason='Initial consult',
        provider_id=pk(provider),
    )

    appointment.refresh_from_db()
    assert appointment.provider_id == pk(provider)


@pytest.mark.django_db
def test_book_appointment_raises_when_slot_outside_provider_availability():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='outside-slot-user',
        password='safe-password-123',
        insurance_tier='Bronze',
        medical_history={},
    )
    provider = make_provider()

    with pytest.raises(ValueError, match='not within provider'):
        book_appointment(
            user_id=pk(user),
            time_slot='2026-04-10T08:00:00',
            symptoms_summary='Sore throat',
            appointment_reason='Initial consult',
            provider_id=pk(provider),
        )


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
    provider = make_provider()

    book_appointment(
        user_id=pk(user_a),
        time_slot='2026-04-10T09:00:00',
        symptoms_summary='Fever',
        appointment_reason='Checkup',
        provider_id=pk(provider),
    )

    with pytest.raises(ValueError, match='already booked'):
        book_appointment(
            user_id=pk(user_b),
            time_slot='2026-04-10T09:00:00',
            symptoms_summary='Cough',
            appointment_reason='Checkup',
            provider_id=pk(provider),
        )


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
        user_id=pk(user),
        time_slot='2026-04-12T09:00:00',
        symptoms_summary='Headache',
        appointment_reason='Assessment',
    )

    assert appointment.provider_id is None


@pytest.mark.django_db
def test_book_appointment_reschedule_with_appointment_id_changes_provider():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='reschedule-provider-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )
    provider_a = make_provider('Dr. A', 'General')
    provider_b = make_provider('Dr. B', 'General')

    appointment = book_appointment(
        user_id=pk(user),
        time_slot='2026-04-10T09:00:00',
        symptoms_summary='Fever',
        appointment_reason='Checkup',
        provider_id=pk(provider_a),
    )

    rescheduled = book_appointment(
        user_id=pk(user),
        appointment_id=pk(appointment),
        time_slot='2026-04-10T10:00:00',
        symptoms_summary='Fever',
        appointment_reason='Checkup',
        provider_id=pk(provider_b),
    )

    assert pk(rescheduled) == pk(appointment)
    rescheduled.refresh_from_db()
    assert rescheduled.provider_id == pk(provider_b)
    assert Appointment.objects.filter(user_id=pk(user)).count() == 1
