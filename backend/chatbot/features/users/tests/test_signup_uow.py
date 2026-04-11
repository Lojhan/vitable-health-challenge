import pytest
from django.contrib.auth import get_user_model

from chatbot.features.core.models import OutboxMessage
from chatbot.features.users.application.signup import UserSignedUpEvent
from chatbot.features.users.infrastructure.unit_of_work.django_signup import (
    DjangoSignUpUnitOfWork,
)


@pytest.mark.django_db
def test_signup_uow_deduplicates_duplicate_recorded_event_by_idempotency_key():
    user_model = get_user_model()
    uow = DjangoSignUpUnitOfWork(user_model)

    with uow as unit:
        user = unit.create_user(
            email='uow-duplicate@example.com',
            password='safe-password-123',
            first_name='Uow',
            insurance_tier='Silver',
        )

        event = UserSignedUpEvent(
            user_id=int(user.id),
            email=user.email,
            first_name=user.first_name,
            insurance_tier=user.insurance_tier,
        )

        unit.record_event(event)
        unit.record_event(event)

    outbox_rows = OutboxMessage.objects.filter(event_type='users.user_signed_up')

    assert outbox_rows.count() == 1
    row = outbox_rows.get()
    assert row.aggregate_id == str(user.id)
    assert row.payload['email'] == 'uow-duplicate@example.com'


@pytest.mark.django_db
def test_signup_uow_uses_deterministic_outbox_idempotency_key():
    user_model = get_user_model()
    uow = DjangoSignUpUnitOfWork(user_model)

    with uow as unit:
        user = unit.create_user(
            email='uow-key@example.com',
            password='safe-password-123',
            first_name='Key',
            insurance_tier='Gold',
        )
        unit.record_event(
            UserSignedUpEvent(
                user_id=int(user.id),
                email=user.email,
                first_name=user.first_name,
                insurance_tier=user.insurance_tier,
            )
        )

    outbox = OutboxMessage.objects.get(event_type='users.user_signed_up')
    assert outbox.idempotency_key == (
        f'users.user:{user.id}:users.user_signed_up'
    )


@pytest.mark.django_db
def test_signup_uow_logs_when_duplicate_outbox_event_is_suppressed(caplog):
    user_model = get_user_model()

    with DjangoSignUpUnitOfWork(user_model) as unit:
        user = unit.create_user(
            email='uow-log@example.com',
            password='safe-password-123',
            first_name='Log',
            insurance_tier='Silver',
        )
        unit.record_event(
            UserSignedUpEvent(
                user_id=int(user.id),
                email=user.email,
                first_name=user.first_name,
                insurance_tier=user.insurance_tier,
            )
        )

    event = UserSignedUpEvent(
        user_id=int(user.id),
        email=user.email,
        first_name=user.first_name,
        insurance_tier=user.insurance_tier,
    )

    with caplog.at_level('INFO'):
        with DjangoSignUpUnitOfWork(user_model) as unit:
            unit.record_event(event)

    assert OutboxMessage.objects.filter(event_type='users.user_signed_up').count() == 1
    assert 'users.signup.outbox_duplicate_suppressed' in caplog.text
