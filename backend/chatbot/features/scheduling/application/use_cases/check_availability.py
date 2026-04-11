from collections.abc import Callable
from datetime import timedelta

from dateutil.rrule import rrulestr

from chatbot.features.core.application.contracts import BaseUseCase
from chatbot.features.core.domain.validation import require_non_blank_text
from chatbot.features.scheduling.application.common import (
    display_datetime,
    normalize_datetime,
    resolve_date_range_input,
)
from chatbot.features.scheduling.application.unit_of_work import SchedulingUnitOfWork


class CheckAvailabilityUseCase(BaseUseCase):
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
    ) -> list[str]:
        normalized_date_range_str = require_non_blank_text(
            date_range_str,
            field='date_range_str',
        )
        start, end = resolve_date_range_input(normalized_date_range_str)

        with self._uow_factory() as uow:
            if provider_id is not None:
                provider = uow.get_provider(provider_id)
                if provider is None:
                    return []

                provider_rule = rrulestr(
                    provider.availability_rrule, dtstart=provider.availability_dtstart
                )
                available_provider_slots = {
                    display_datetime(normalize_datetime(occ))
                    for occ in provider_rule.between(start, end, inc=True)
                }

                occupied: set[str] = set()
                for appointment in uow.list_provider_appointments(provider_id):
                    rule = rrulestr(appointment.rrule, dtstart=appointment.time_slot)
                    for occurrence in rule.between(start, end, inc=True):
                        occupied.add(display_datetime(normalize_datetime(occurrence)))

                return sorted(available_provider_slots - occupied)

            occupied_open: set[str] = set()
            for appointment in uow.list_all_appointments():
                rule = rrulestr(appointment.rrule, dtstart=appointment.time_slot)
                for occurrence in rule.between(start, end, inc=True):
                    occupied_open.add(display_datetime(normalize_datetime(occurrence)))

        available_slots: list[str] = []
        current = start
        while current < end:
            candidate = display_datetime(current)
            if candidate not in occupied_open:
                available_slots.append(candidate)
            current += timedelta(hours=1)

        return available_slots
