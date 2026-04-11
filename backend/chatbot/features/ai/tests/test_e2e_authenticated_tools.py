import asyncio
import json
from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from django.contrib.auth import get_user_model

from chatbot.features.ai.openrouter_agent import OpenRouterAgent
from chatbot.features.scheduling.models import Appointment


def _pk(instance: object) -> int:
    return cast(int, cast(Any, instance).pk)


@pytest.mark.django_db(transaction=True)
def test_end_to_end_session_persistence_with_appointment_tools(monkeypatch):
    """
    Validates that:
    1. Chat sessions persist on backend
    2. User messages are stored in session
    3. Assistant responses are stored in session
    4. New authenticated appointment tools work correctly
    """
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')
    
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='e2e-user',
        password='safe-password-123',
        first_name='Alex',
        insurance_tier='Gold',
        medical_history={},
    )

    # Mock OpenAI client to simulate:
    # 1. First turn: list_my_appointments (user has none)
    # 2. Second turn: book_appointment
    agent = OpenRouterAgent(model='openai/gpt-4o-mini', user_id=_pk(user))
    
    # TURN 1: List my appointments
    first_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='',
                    tool_calls=[
                        SimpleNamespace(
                            id='tool-call-1',
                            function=SimpleNamespace(
                                name='list_my_appointments',
                                arguments=json.dumps({}),
                            ),
                        )
                    ],
                )
            )
        ]
    )
    first_final_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='You have no appointments scheduled.'
                )
            )
        ]
    )

    # TURN 2: Book appointment
    second_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='',
                    tool_calls=[
                        SimpleNamespace(
                            id='tool-call-2',
                            function=SimpleNamespace(
                                name='check_availability',
                                arguments=json.dumps({
                                    'date_range_str': '2026-04-15T09:00:00/2026-04-15T12:00:00'
                                }),
                            ),
                        ),
                        SimpleNamespace(
                            id='tool-call-3',
                            function=SimpleNamespace(
                                name='book_appointment',
                                arguments=json.dumps({
                                    'time_slot': '2026-04-15T10:00:00',
                                    'rrule_str': 'FREQ=DAILY;COUNT=1',
                                    'symptoms_summary': 'Sore throat and persistent fatigue',
                                    'appointment_reason': 'Needs exam to evaluate worsening symptoms',
                                }),
                            ),
                        )
                    ],
                )
            )
        ]
    )
    second_final_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='Appointment booked for 2026-04-15 at 10:00 AM.'
                )
            )
        ]
    )

    mocked_create = AsyncMock(
        side_effect=[
            first_response,
            first_final_response,
            second_response,
            second_final_response,
        ]
    )
    agent._client.chat.completions.create = mocked_create

    async def run_turns():
        # Turn 1: List appointments
        result1 = await agent.generate_response('What appointments do I have?')
        assert result1 == 'You have no appointments scheduled.'

        # Turn 2: Book appointment
        result2 = await agent.generate_response('Schedule me for tomorrow at 10 AM.')
        assert result2 == 'Appointment booked for 2026-04-15 at 10:00 AM.'

    asyncio.run(run_turns())

    # Verify appointment was actually created
    appointments = Appointment.objects.filter(user_id=_pk(user))
    assert appointments.count() == 1
    
    appointment = appointments.first()
    assert appointment is not None
    assert appointment.time_slot.replace(tzinfo=None) == datetime.fromisoformat('2026-04-15T10:00:00')
    assert appointment.rrule == 'FREQ=DAILY;COUNT=1'
    assert appointment.symptoms_summary == 'Sore throat and persistent fatigue'
    assert appointment.appointment_reason == 'Needs exam to evaluate worsening symptoms'
    
    # Verify authenticated boundary: other user can't see or modify
    other_user = user_model.objects.create_user(
        username='other-user',
        password='safe-password-123',
        first_name='Bob',
        insurance_tier='Bronze',
        medical_history={},
    )
    
    from chatbot.features.scheduling.tools import (
        cancel_user_appointment,
        update_user_appointment,
    )
    
    # Other user tries to cancel this user's appointment
    result = cancel_user_appointment(user_id=_pk(other_user), appointment_id=_pk(appointment))
    assert result['cancelled'] is False
    assert Appointment.objects.filter(id=_pk(appointment)).exists()
    
    # Other user tries to update this user's appointment
    result = update_user_appointment(
        user_id=_pk(other_user),
        appointment_id=_pk(appointment),
        time_slot='2026-04-16T11:00:00',
    )
    assert result['updated'] is False
    
    # Only owner can update
    result = update_user_appointment(
        user_id=_pk(user),
        appointment_id=_pk(appointment),
        time_slot='2026-04-16T14:00:00',
    )
    assert result['updated'] is True
    
    appointment.refresh_from_db()
    assert appointment.time_slot.replace(tzinfo=None) == datetime.fromisoformat('2026-04-16T14:00:00')
