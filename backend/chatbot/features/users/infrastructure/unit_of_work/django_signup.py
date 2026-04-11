from __future__ import annotations

import logging
from dataclasses import asdict
from types import TracebackType
from typing import Any, cast

from django.db import transaction

from chatbot.features.core.application.contracts import BaseUnitOfWork
from chatbot.features.core.models import OutboxMessage
from chatbot.features.users.application.signup import UserSignedUpEvent

logger = logging.getLogger(__name__)


class DjangoSignUpUnitOfWork(BaseUnitOfWork):
    def __init__(self, user_model: Any) -> None:
        self._user_model = user_model
        self._atomic = None
        self._events: list[UserSignedUpEvent] = []

    def __enter__(self) -> DjangoSignUpUnitOfWork:
        self._events = []
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

        if exc_type is not None:
            self._events = []
            return self._atomic.__exit__(exc_type, exc, tb)

        try:
            for event in self._events:
                outbox_message, created = OutboxMessage.objects.get_or_create(
                    idempotency_key=OutboxMessage.build_idempotency_key(
                        aggregate_type=event.aggregate_type,
                        aggregate_id=event.aggregate_id,
                        event_type=event.event_type,
                    ),
                    defaults={
                        'aggregate_type': event.aggregate_type,
                        'aggregate_id': event.aggregate_id,
                        'event_type': event.event_type,
                        'payload': asdict(event),
                    },
                )
                if not created:
                    logger.info(
                        'users.signup.outbox_duplicate_suppressed',
                        extra={
                            'outbox_id': cast(int, cast(Any, outbox_message).id),
                            'event_type': outbox_message.event_type,
                            'aggregate_id': outbox_message.aggregate_id,
                            'idempotency_key': outbox_message.idempotency_key,
                        },
                    )
        except Exception as error:
            self._events = []
            self._atomic.__exit__(type(error), error, error.__traceback__)
            raise

        self._events = []
        return self._atomic.__exit__(None, None, None)

    def email_exists(self, email: str) -> bool:
        return self._user_model.objects.filter(email=email).exists()

    def create_user(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        insurance_tier: str,
    ) -> Any:
        return self._user_model.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            insurance_tier=insurance_tier,
        )

    def record_event(self, event: UserSignedUpEvent) -> None:
        self._events.append(event)
