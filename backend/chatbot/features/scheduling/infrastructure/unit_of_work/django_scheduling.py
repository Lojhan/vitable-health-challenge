from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Any

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import F

from chatbot.features.core.application.contracts import BaseUnitOfWork
from chatbot.features.scheduling.models import Appointment, Provider


class DjangoSchedulingUnitOfWork(BaseUnitOfWork):
    def __init__(self) -> None:
        self._atomic = None

    def __enter__(self) -> DjangoSchedulingUnitOfWork:
        self._atomic = transaction.atomic()
        self._atomic.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        if self._atomic is None:
            raise RuntimeError('Unit of work was not entered before exit.')
        return self._atomic.__exit__(exc_type, exc, tb)

    def get_user(self, user_id: int) -> Any:
        user_model = get_user_model()
        return user_model.objects.get(id=user_id)

    def get_provider(self, provider_id: int) -> Provider | None:
        return Provider.objects.filter(pk=provider_id).first()

    def list_providers(self) -> list[Provider]:
        return list(Provider.objects.all().order_by('name'))

    def list_all_appointments(self) -> list[Appointment]:
        return list(Appointment.objects.all())

    def list_provider_appointments(self, provider_id: int) -> list[Appointment]:
        return list(Appointment.objects.filter(provider_id=provider_id))

    def list_future_user_appointments(
        self,
        *,
        user_id: int,
        from_datetime: datetime,
    ) -> list[Appointment]:
        return list(
            Appointment.objects.select_related('provider')
            .filter(user_id=user_id, time_slot__gte=from_datetime)
            .order_by('time_slot', 'id')
        )

    def provider_has_conflict(
        self,
        *,
        provider_id: int,
        time_slot: datetime,
        exclude_appointment_id: int | None = None,
    ) -> bool:
        query = Appointment.objects.filter(provider_id=provider_id, time_slot=time_slot)
        if exclude_appointment_id is not None:
            query = query.exclude(id=exclude_appointment_id)
        return query.exists()

    def get_user_appointment(self, *, user_id: int, appointment_id: int) -> Appointment | None:
        return (
            Appointment.objects.select_related('provider')
            .select_for_update(of=('self',))
            .filter(id=appointment_id, user_id=user_id)
            .first()
        )

    def create_appointment(self, **kwargs: Any) -> Appointment:
        try:
            return Appointment.objects.create(**kwargs)
        except IntegrityError as error:
            if kwargs.get('provider') is not None:
                raise ValueError('Provider is already booked at this time slot.') from error
            raise

    def save_appointment(self, appointment: Appointment, *, update_fields: list[str]) -> None:
        current_version = appointment.version
        update_values = {
            field_name: getattr(appointment, field_name)
            for field_name in update_fields
        }
        update_values['version'] = F('version') + 1

        try:
            updated_count = Appointment.objects.filter(
                id=appointment.id,
                version=current_version,
            ).update(**update_values)
        except IntegrityError as error:
            if 'provider' in update_fields:
                raise ValueError('Provider is already booked at this time slot.') from error
            raise

        if updated_count == 0:
            raise ValueError('Appointment update conflict detected; please retry.')

        appointment.version = current_version + 1

    def delete_user_appointment(self, *, user_id: int, appointment_id: int) -> bool:
        deleted_count, _ = Appointment.objects.filter(
            id=appointment_id,
            user_id=user_id,
        ).delete()
        return deleted_count > 0
