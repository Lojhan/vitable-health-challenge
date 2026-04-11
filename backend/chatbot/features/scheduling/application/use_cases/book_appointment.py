from collections.abc import Callable

from dateutil.rrule import rrulestr

from chatbot.features.core.application.contracts import BaseUseCase
from chatbot.features.core.domain.validation import require_non_blank_text, require_positive_int
from chatbot.features.scheduling.application.common import (
    coerce_appointment_id,
    parse_datetime_input,
)
from chatbot.features.scheduling.application.unit_of_work import SchedulingUnitOfWork
from chatbot.features.scheduling.models import Appointment


class BookAppointmentUseCase(BaseUseCase):
    def __init__(
        self,
        *,
        uow_factory: Callable[[], SchedulingUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(
        self,
        *,
        user_id: int,
        time_slot: str,
        rrule_str: str | None = None,
        symptoms_summary: str,
        appointment_reason: str,
        appointment_id: int | str | None = None,
        provider_id: int | None = None,
    ) -> Appointment:
        require_positive_int(user_id, field='user_id')
        normalized_time_slot = require_non_blank_text(time_slot, field='time_slot')
        normalized_symptoms_summary = require_non_blank_text(
            symptoms_summary,
            field='symptoms_summary',
        )
        normalized_appointment_reason = require_non_blank_text(
            appointment_reason,
            field='appointment_reason',
        )

        parsed_time_slot = parse_datetime_input(normalized_time_slot)
        normalized_appointment_id = coerce_appointment_id(appointment_id)

        with self._uow_factory() as uow:
            user = uow.get_user(user_id)

            resolved_provider = None
            if provider_id is not None:
                resolved_provider = uow.get_provider(provider_id)
                if resolved_provider is None:
                    raise ValueError(f'Provider {provider_id} does not exist')

                provider_rule = rrulestr(
                    resolved_provider.availability_rrule,
                    dtstart=resolved_provider.availability_dtstart,
                )
                if not provider_rule.between(parsed_time_slot, parsed_time_slot, inc=True):
                    raise ValueError(
                        f'Time slot is not within provider {resolved_provider.name} availability'
                    )

                if uow.provider_has_conflict(
                    provider_id=provider_id,
                    time_slot=parsed_time_slot,
                    exclude_appointment_id=normalized_appointment_id,
                ):
                    raise ValueError(
                        f'Provider {resolved_provider.name} is already booked at {normalized_time_slot}'
                    )

            if normalized_appointment_id is not None:
                existing = uow.get_user_appointment(
                    user_id=user_id,
                    appointment_id=normalized_appointment_id,
                )
                if existing is not None:
                    existing.time_slot = parsed_time_slot
                    existing.rrule = rrule_str or existing.rrule
                    existing.symptoms_summary = normalized_symptoms_summary
                    existing.appointment_reason = normalized_appointment_reason
                    update_fields = [
                        'time_slot',
                        'rrule',
                        'symptoms_summary',
                        'appointment_reason',
                    ]
                    if resolved_provider is not None:
                        existing.provider = resolved_provider
                        update_fields.append('provider')

                    uow.save_appointment(existing, update_fields=update_fields)
                    return existing

            return uow.create_appointment(
                user=user,
                title='Booked Appointment',
                time_slot=parsed_time_slot,
                rrule=rrule_str or 'FREQ=DAILY;COUNT=1',
                symptoms_summary=normalized_symptoms_summary,
                appointment_reason=normalized_appointment_reason,
                provider=resolved_provider,
            )
