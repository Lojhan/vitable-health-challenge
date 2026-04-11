import pytest
from django.core.management import call_command
from django.utils import timezone

from chatbot.features.core.models import OutboxMessage


def _key(suffix: str) -> str:
    return f'test-key:{suffix}'


@pytest.mark.django_db
def test_outbox_message_defaults_include_retry_and_error_state():
    message = OutboxMessage.objects.create(
        aggregate_type='users.user',
        aggregate_id='1',
        event_type='users.user_signed_up',
        idempotency_key=_key('defaults'),
        payload={'user_id': 1},
    )

    assert message.retry_count == 0
    assert message.error == ''
    assert message.published_at is None


@pytest.mark.django_db
def test_outbox_pending_query_only_returns_unpublished_ordered_by_id():
    first_pending = OutboxMessage.objects.create(
        aggregate_type='users.user',
        aggregate_id='1',
        event_type='users.user_signed_up',
        idempotency_key=_key('pending-1'),
        payload={'user_id': 1},
    )
    published = OutboxMessage.objects.create(
        aggregate_type='users.user',
        aggregate_id='2',
        event_type='users.user_signed_up',
        idempotency_key=_key('pending-2'),
        payload={'user_id': 2},
        published_at=timezone.now(),
    )
    second_pending = OutboxMessage.objects.create(
        aggregate_type='users.user',
        aggregate_id='3',
        event_type='users.user_signed_up',
        idempotency_key=_key('pending-3'),
        payload={'user_id': 3},
    )

    pending_ids = list(OutboxMessage.objects.pending().values_list('id', flat=True))

    assert pending_ids == [first_pending.id, second_pending.id]
    assert published.id not in pending_ids


@pytest.mark.django_db
def test_publish_outbox_command_marks_messages_as_published(monkeypatch):
    first = OutboxMessage.objects.create(
        aggregate_type='users.user',
        aggregate_id='1',
        event_type='users.user_signed_up',
        idempotency_key=_key('publish-ok-1'),
        payload={'user_id': 1},
    )
    second = OutboxMessage.objects.create(
        aggregate_type='users.user',
        aggregate_id='2',
        event_type='users.user_signed_up',
        idempotency_key=_key('publish-ok-2'),
        payload={'user_id': 2},
    )

    handled_ids = []

    def fake_dispatch(message):
        handled_ids.append(message.id)

    monkeypatch.setattr(
        'chatbot.features.core.management.commands.publish_outbox.dispatch_outbox_message',
        fake_dispatch,
    )

    call_command('publish_outbox', batch_size=1)

    first.refresh_from_db()
    second.refresh_from_db()

    assert handled_ids == [first.id]
    assert first.published_at is not None
    assert first.retry_count == 0
    assert first.error == ''
    assert second.published_at is None


@pytest.mark.django_db
def test_publish_outbox_command_tracks_failures_and_retries(monkeypatch):
    message = OutboxMessage.objects.create(
        aggregate_type='users.user',
        aggregate_id='1',
        event_type='users.user_signed_up',
        idempotency_key=_key('publish-fail'),
        payload={'user_id': 1},
    )

    def fake_dispatch(_message):
        raise RuntimeError('dispatcher unavailable')

    monkeypatch.setattr(
        'chatbot.features.core.management.commands.publish_outbox.dispatch_outbox_message',
        fake_dispatch,
    )

    call_command('publish_outbox')

    message.refresh_from_db()

    assert message.published_at is None
    assert message.retry_count == 1
    assert message.error == 'dispatcher unavailable'


@pytest.mark.django_db
def test_publish_outbox_command_skips_messages_at_or_above_max_retries(monkeypatch):
    skipped = OutboxMessage.objects.create(
        aggregate_type='users.user',
        aggregate_id='1',
        event_type='users.user_signed_up',
        idempotency_key=_key('max-retries-skip'),
        payload={'user_id': 1},
        retry_count=2,
    )
    processed = OutboxMessage.objects.create(
        aggregate_type='users.user',
        aggregate_id='2',
        event_type='users.user_signed_up',
        idempotency_key=_key('max-retries-process'),
        payload={'user_id': 2},
        retry_count=1,
    )

    handled_ids = []

    def fake_dispatch(message):
        handled_ids.append(message.id)

    monkeypatch.setattr(
        'chatbot.features.core.management.commands.publish_outbox.dispatch_outbox_message',
        fake_dispatch,
    )

    call_command('publish_outbox', max_retries=2)

    skipped.refresh_from_db()
    processed.refresh_from_db()

    assert handled_ids == [processed.id]
    assert skipped.published_at is None
    assert processed.published_at is not None


@pytest.mark.django_db
def test_publish_outbox_command_filters_by_event_type(monkeypatch):
    user_event = OutboxMessage.objects.create(
        aggregate_type='users.user',
        aggregate_id='1',
        event_type='users.user_signed_up',
        idempotency_key=_key('filter-user'),
        payload={'user_id': 1},
    )
    appointment_event = OutboxMessage.objects.create(
        aggregate_type='scheduling.appointment',
        aggregate_id='10',
        event_type='scheduling.appointment_booked',
        idempotency_key=_key('filter-appointment'),
        payload={'appointment_id': 10},
    )

    handled_ids = []

    def fake_dispatch(message):
        handled_ids.append(message.id)

    monkeypatch.setattr(
        'chatbot.features.core.management.commands.publish_outbox.dispatch_outbox_message',
        fake_dispatch,
    )

    call_command('publish_outbox', event_type='users.user_signed_up')

    user_event.refresh_from_db()
    appointment_event.refresh_from_db()

    assert handled_ids == [user_event.id]
    assert user_event.published_at is not None
    assert appointment_event.published_at is None


@pytest.mark.django_db
def test_outbox_pending_query_excludes_dead_lettered_messages():
    active = OutboxMessage.objects.create(
        aggregate_type='users.user',
        aggregate_id='1',
        event_type='users.user_signed_up',
        idempotency_key=_key('dead-letter-active'),
        payload={'user_id': 1},
    )
    dead_lettered = OutboxMessage.objects.create(
        aggregate_type='users.user',
        aggregate_id='2',
        event_type='users.user_signed_up',
        idempotency_key=_key('dead-letter-archived'),
        payload={'user_id': 2},
        dead_lettered_at=timezone.now(),
    )

    pending_ids = list(OutboxMessage.objects.pending().values_list('id', flat=True))

    assert active.id in pending_ids
    assert dead_lettered.id not in pending_ids


@pytest.mark.django_db
def test_publish_outbox_command_marks_dead_letter_after_threshold(monkeypatch):
    message = OutboxMessage.objects.create(
        aggregate_type='users.user',
        aggregate_id='1',
        event_type='users.user_signed_up',
        idempotency_key=_key('dead-letter-threshold'),
        payload={'user_id': 1},
        retry_count=1,
    )

    def fake_dispatch(_message):
        raise RuntimeError('permanent failure')

    monkeypatch.setattr(
        'chatbot.features.core.management.commands.publish_outbox.dispatch_outbox_message',
        fake_dispatch,
    )

    call_command('publish_outbox', dead_letter_after=2)

    message.refresh_from_db()

    assert message.retry_count == 2
    assert message.dead_lettered_at is not None
