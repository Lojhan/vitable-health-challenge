from collections.abc import Callable

from django.utils import timezone

from chatbot.features.core.application.contracts import BaseUseCase
from chatbot.features.core.domain.validation import require_positive_int
from chatbot.features.scheduling.application.common import (
    FutureAppointmentsPayload,
    format_future_appointments_payload,
)
from chatbot.features.scheduling.application.unit_of_work import SchedulingUnitOfWork


class ListUserAppointmentsUseCase(BaseUseCase):
    def __init__(
        self,
        *,
        uow_factory: Callable[[], SchedulingUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(self, *, user_id: int) -> FutureAppointmentsPayload:
        require_positive_int(user_id, field='user_id')
        with self._uow_factory() as uow:
            appointments = uow.list_future_user_appointments(
                user_id=user_id,
                from_datetime=timezone.now(),
            )
        return format_future_appointments_payload(appointments)
