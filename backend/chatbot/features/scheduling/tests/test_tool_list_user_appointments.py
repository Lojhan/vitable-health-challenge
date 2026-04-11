from datetime import UTC, datetime

import pytest
from django.contrib.auth import get_user_model

from chatbot.features.scheduling.models import Appointment
from chatbot.features.scheduling.tests.helpers import make_provider, pk
from chatbot.features.scheduling.tools import list_user_appointments


@pytest.mark.django_db
def test_list_user_appointments_returns_empty_formatted_payload_when_none_exist():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='empty-list-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )

    appointments = list_user_appointments(user_id=pk(user))

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
        time_slot=datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC),
        rrule='FREQ=DAILY;COUNT=1',
    )
    Appointment.objects.create(
        user=other_user,
        title='Other',
        time_slot=datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC),
        rrule='FREQ=DAILY;COUNT=1',
    )

    appointments = list_user_appointments(user_id=pk(user))

    assert appointments['count'] == 1
    assert appointments['summary'] == 'You have 1 upcoming appointment(s).'
    assert appointments['appointments'] == [
        {
            'appointment_id': pk(first),
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
def test_list_user_appointments_serializes_provider_info_when_set():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='serialize-provider-user',
        password='safe-password-123',
        insurance_tier='Gold',
        medical_history={},
    )
    provider = make_provider()
    Appointment.objects.create(
        user=user,
        title='Booked Appointment',
        time_slot=datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC),
        rrule='FREQ=DAILY;COUNT=1',
        provider=provider,
    )

    result = list_user_appointments(user_id=pk(user))

    assert result['count'] == 1
    serialized = result['appointments'][0]
    assert serialized['provider_id'] == pk(provider)
    assert serialized['provider_name'] == 'Dr. Alice Smith'


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
        time_slot=datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC),
        rrule='FREQ=DAILY;COUNT=1',
    )

    result = list_user_appointments(user_id=pk(user))

    assert result['count'] == 1
    serialized = result['appointments'][0]
    assert serialized['provider_id'] is None
    assert serialized['provider_name'] is None
