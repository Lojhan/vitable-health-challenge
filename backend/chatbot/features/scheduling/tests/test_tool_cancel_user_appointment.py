from datetime import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from chatbot.features.scheduling.models import Appointment
from chatbot.features.scheduling.tests.helpers import pk
from chatbot.features.scheduling.tools import cancel_user_appointment, update_user_appointment


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

    cancelled = cancel_user_appointment(user_id=pk(user), appointment_id=pk(own_appointment))
    denied = cancel_user_appointment(user_id=pk(user), appointment_id=pk(others_appointment))

    assert cancelled == {'appointment_id': pk(own_appointment), 'cancelled': True}
    assert denied == {'appointment_id': pk(others_appointment), 'cancelled': False}
    assert Appointment.objects.filter(id=pk(own_appointment)).exists() is False
    assert Appointment.objects.filter(id=pk(others_appointment)).exists() is True


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
        user_id=pk(user),
        appointment_id=f'Appointment #{pk(appointment)}:',
        time_slot='2026-04-18T11:00:00',
    )
    assert update_result['updated'] is True

    cancel_result = cancel_user_appointment(
        user_id=pk(user),
        appointment_id=f'#{pk(appointment)}',
    )
    assert cancel_result == {'appointment_id': pk(appointment), 'cancelled': True}
    assert Appointment.objects.filter(id=pk(appointment)).exists() is False
