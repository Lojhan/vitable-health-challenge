from collections.abc import Callable

from chatbot.features.core.application.contracts import BaseUseCase
from chatbot.features.core.domain.validation import require_positive_int
from chatbot.features.scheduling.application.common import (
    CancelAppointmentResult,
    coerce_appointment_id,
)
from chatbot.features.scheduling.application.unit_of_work import SchedulingUnitOfWork


class CancelUserAppointmentUseCase(BaseUseCase):
    def __init__(
        self,
        *,
        uow_factory: Callable[[], SchedulingUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(self, *, user_id: int, appointment_id: int | str) -> CancelAppointmentResult:
        require_positive_int(user_id, field='user_id')
        normalized_appointment_id = coerce_appointment_id(appointment_id)
        if normalized_appointment_id is None:
            return {
                'appointment_id': -1,
                'cancelled': False,
            }

        with self._uow_factory() as uow:
            cancelled = uow.delete_user_appointment(
                user_id=user_id,
                appointment_id=normalized_appointment_id,
            )

        return {
            'appointment_id': normalized_appointment_id,
            'cancelled': cancelled,
        }
