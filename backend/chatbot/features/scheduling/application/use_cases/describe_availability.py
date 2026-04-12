from collections.abc import Callable
from datetime import timedelta

from dateutil.rrule import rrulestr

from chatbot.features.core.application.contracts import BaseUseCase
from chatbot.features.core.domain.validation import require_non_blank_text
from chatbot.features.scheduling.application.common import (
    AvailabilityPayload,
    display_datetime,
    normalize_datetime,
    resolve_date_range_input,
)
from chatbot.features.scheduling.application.unit_of_work import SchedulingUnitOfWork


class DescribeAvailabilityUseCase(BaseUseCase):
    def __init__(
        self,
        *,
        uow_factory: Callable[[], SchedulingUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(
        self,
        *,
        date_range_str: str,
        provider_id: int | None = None,
    ) -> AvailabilityPayload:
        normalized_date_range_str = require_non_blank_text(
            date_range_str,
            field='date_range_str',
        )
        start, end = resolve_date_range_input(normalized_date_range_str)

        payload: AvailabilityPayload = {
            'type': 'availability',
            'timezone': 'UTC',
            'appointment_duration_minutes': 60,
            'appointment_duration_note': '*Appointments last 1h.',
            'requested_window_start_utc': display_datetime(start),
            'requested_window_end_utc': display_datetime(end),
            'blocked_slots_utc': [],
        }

        with self._uow_factory() as uow:
            if provider_id is not None:
                provider = uow.get_provider(provider_id)
                if provider is None:
                    payload['availability_source'] = 'provider_rrule'
                    payload['provider'] = None
                    payload['availability_dtstart_utc'] = None
                    payload['availability_rrule'] = None
                    return payload

                blocked_slots_utc: set[str] = set()
                for appointment in uow.list_provider_appointments(provider_id):
                    rule = rrulestr(appointment.rrule, dtstart=appointment.time_slot)
                    for occurrence in rule.between(start, end, inc=True):
                        blocked_slots_utc.add(
                            display_datetime(normalize_datetime(occurrence))
                        )

                payload['availability_source'] = 'provider_rrule'
                payload['provider'] = {
                    'provider_id': int(provider.pk),
                    'name': provider.name,
                    'specialty': provider.specialty,
                }
                payload['availability_dtstart_utc'] = display_datetime(
                    normalize_datetime(provider.availability_dtstart)
                )
                payload['availability_rrule'] = provider.availability_rrule
                payload['blocked_slots_utc'] = sorted(blocked_slots_utc)
                return payload

            occupied_slots_utc: set[str] = set()
            for appointment in uow.list_all_appointments():
                rule = rrulestr(appointment.rrule, dtstart=appointment.time_slot)
                for occurrence in rule.between(start, end, inc=True):
                    occupied_slots_utc.add(
                        display_datetime(normalize_datetime(occurrence))
                    )

        available_slots_utc: list[str] = []
        current = start
        while current < end:
            candidate = display_datetime(current)
            if candidate not in occupied_slots_utc:
                available_slots_utc.append(candidate)
            current += timedelta(hours=1)

        payload['availability_source'] = 'open_slots'
        payload['provider'] = None
        payload['availability_dtstart_utc'] = None
        payload['availability_rrule'] = None
        payload['available_slots_utc'] = available_slots_utc
        return payload