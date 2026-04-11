from collections.abc import Callable

from dateutil.rrule import rrulestr

from chatbot.features.core.application.contracts import BaseUseCase
from chatbot.features.core.domain.validation import require_non_blank_text, require_positive_int
from chatbot.features.scheduling.application.common import (
    UpdateAppointmentResult,
    coerce_appointment_id,
    normalize_datetime,
    parse_datetime_input,
    serialize_appointment,
)
from chatbot.features.scheduling.application.unit_of_work import SchedulingUnitOfWork


class UpdateUserAppointmentUseCase(BaseUseCase):
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
        appointment_id: int | str,
        time_slot: str | None = None,
        rrule_str: str | None = None,
        symptoms_summary: str | None = None,
        appointment_reason: str | None = None,
        provider_id: int | None = None,
    ) -> UpdateAppointmentResult:
        require_positive_int(user_id, field='user_id')
        normalized_appointment_id = coerce_appointment_id(appointment_id)
        if normalized_appointment_id is None:
            return {
                'appointment_id': -1,
                'updated': False,
                'reason': 'invalid_appointment_id',
            }

        with self._uow_factory() as uow:
            appointment = uow.get_user_appointment(
                user_id=user_id,
                appointment_id=normalized_appointment_id,
            )

            if appointment is None:
                return {
                    'appointment_id': normalized_appointment_id,
                    'updated': False,
                    'reason': 'not_found',
                }

            if time_slot is not None:
                appointment.time_slot = parse_datetime_input(
                    require_non_blank_text(time_slot, field='time_slot')
                )

            if rrule_str is not None:
                appointment.rrule = rrule_str

            if symptoms_summary is not None:
                appointment.symptoms_summary = require_non_blank_text(
                    symptoms_summary,
                    field='symptoms_summary',
                )

            if appointment_reason is not None:
                appointment.appointment_reason = require_non_blank_text(
                    appointment_reason,
                    field='appointment_reason',
                )

            update_fields: list[str] = [
                'time_slot',
                'rrule',
                'symptoms_summary',
                'appointment_reason',
            ]

            if provider_id is not None:
                new_provider = uow.get_provider(provider_id)
                if new_provider is None:
                    return {
                        'appointment_id': normalized_appointment_id,
                        'updated': False,
                        'reason': 'invalid_provider_id',
                    }

                effective_slot = normalize_datetime(appointment.time_slot)
                provider_rule = rrulestr(
                    new_provider.availability_rrule,
                    dtstart=new_provider.availability_dtstart,
                )
                if not provider_rule.between(effective_slot, effective_slot, inc=True):
                    raise ValueError(
                        f'Time slot is not within provider {new_provider.name} availability'
                    )

                appointment.provider = new_provider
                update_fields.append('provider')

            uow.save_appointment(appointment, update_fields=update_fields)

            return {
                'appointment_id': int(appointment.pk),
                'updated': True,
                'appointment': serialize_appointment(appointment),
            }
