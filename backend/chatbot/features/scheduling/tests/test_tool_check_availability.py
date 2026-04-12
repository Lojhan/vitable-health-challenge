from datetime import UTC, datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from chatbot.features.scheduling.application.use_cases.check_availability import (
    CheckAvailabilityUseCase,
)
from chatbot.features.scheduling.infrastructure.unit_of_work.django_scheduling import (
    DjangoSchedulingUnitOfWork,
)
from chatbot.features.scheduling.models import Appointment, Provider
from chatbot.features.scheduling.tests.helpers import make_provider


def check_availability(date_range_str: str, provider_id: int | None = None) -> list[str]:
    return CheckAvailabilityUseCase(uow_factory=DjangoSchedulingUnitOfWork).execute(
        date_range_str=date_range_str,
        provider_id=provider_id,
    )


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
def test_check_availability_with_provider_id_returns_only_provider_rrule_slots():
    provider = make_provider()

    slots = check_availability(
        '2026-04-10T08:00:00/2026-04-10T13:00:00',
        provider_id=provider.pk,
    )

    assert '2026-04-10T08:00:00' not in slots
    assert '2026-04-10T09:00:00' in slots
    assert '2026-04-10T10:00:00' in slots
    assert '2026-04-10T11:00:00' in slots
    assert '2026-04-10T12:00:00' not in slots


@pytest.mark.django_db
def test_check_availability_excludes_already_booked_provider_slots():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='provider-avail-booked-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )
    provider = make_provider()
    Appointment.objects.create(
        user=user,
        title='Booked',
        time_slot=datetime(2026, 4, 10, 9, 0, 0, tzinfo=UTC),
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


@pytest.mark.django_db
def test_check_availability_provider_a_booking_does_not_block_provider_b():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='two-provider-avail-user',
        password='safe-password-123',
        insurance_tier='Silver',
        medical_history={},
    )
    provider_a = make_provider('Dr. A', 'General')
    provider_b = make_provider('Dr. B', 'General')
    Appointment.objects.create(
        user=user,
        title='Booked with A',
        time_slot=datetime(2026, 4, 10, 9, 0, 0, tzinfo=UTC),
        rrule='FREQ=DAILY;COUNT=1',
        provider=provider_a,
    )

    slots_b = check_availability(
        '2026-04-10T09:00:00/2026-04-10T11:00:00',
        provider_id=provider_b.pk,
    )

    assert '2026-04-10T09:00:00' in slots_b


@pytest.mark.django_db
def test_check_availability_returns_empty_when_provider_has_no_occurrences_in_range():
    provider = Provider.objects.create(
        name='Dr. Future',
        specialty='Neurology',
        availability_dtstart=datetime(2026, 5, 1, 9, 0, 0, tzinfo=UTC),
        availability_rrule='FREQ=WEEKLY;BYDAY=FR;BYHOUR=9;BYMINUTE=0;BYSECOND=0',
    )

    slots = check_availability(
        '2026-04-10T09:00:00/2026-04-10T12:00:00',
        provider_id=provider.pk,
    )

    assert slots == []


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
