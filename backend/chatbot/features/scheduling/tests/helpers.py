from datetime import UTC, datetime
from typing import Any, cast

from chatbot.features.scheduling.models import Appointment, Provider


def pk(instance: object) -> int:
    return cast(int, cast(Any, instance).pk)


def user_id(appointment: Appointment) -> int:
    return cast(int, cast(Any, appointment).user_id)


def make_provider(
    name: str = 'Dr. Alice Smith',
    specialty: str = 'General Practice',
) -> Provider:
    return Provider.objects.create(
        name=name,
        specialty=specialty,
        availability_dtstart=datetime(2026, 4, 10, 9, 0, 0, tzinfo=UTC),
        availability_rrule='FREQ=DAILY;BYHOUR=9,10,11;BYMINUTE=0;BYSECOND=0',
    )
