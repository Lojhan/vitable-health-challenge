import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from chatbot.features.core.models import OutboxMessage
from chatbot.features.core.outbox_dispatcher import dispatch_outbox_message

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Dispatch and mark pending outbox messages as published'

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Maximum number of pending outbox messages to process',
        )
        parser.add_argument(
            '--max-retries',
            type=int,
            default=5,
            help='Skip outbox messages whose retry_count reached this value',
        )
        parser.add_argument(
            '--event-type',
            type=str,
            default='',
            help='Process only one event type (optional)',
        )
        parser.add_argument(
            '--dead-letter-after',
            type=int,
            default=10,
            help='Move message to dead letter state after this many failures',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        batch_size = max(int(options['batch_size']), 1)
        max_retries = max(int(options['max_retries']), 0)
        event_type = str(options['event_type'] or '').strip()
        dead_letter_after = max(int(options['dead_letter_after']), 1)
        published_count = 0
        failed_count = 0
        dead_lettered_count = 0

        pending_messages = OutboxMessage.objects.pending().filter(retry_count__lt=max_retries)
        if event_type:
            pending_messages = pending_messages.filter(event_type=event_type)

        messages = list(pending_messages[:batch_size])

        for message in messages:
            try:
                dispatch_outbox_message(message)
                message.mark_published(published_at=timezone.now())
                published_count += 1
            except Exception as error:
                failed_at = timezone.now()
                message.mark_failed(
                    error=str(error),
                    failed_at=failed_at,
                    dead_letter_after=dead_letter_after,
                )
                if message.dead_lettered_at is not None:
                    dead_lettered_count += 1
                failed_count += 1
                logger.warning(
                    'outbox.publish.failed',
                    extra={
                        'outbox_id': message.id,
                        'event_type': message.event_type,
                        'retry_count': message.retry_count,
                        'dead_lettered': message.dead_lettered_at is not None,
                    },
                    exc_info=True,
                )

        self.stdout.write(
            self.style.SUCCESS(
                
                    'Outbox publish run complete: '
                    f'published={published_count}, failed={failed_count}, '
                    f'dead_lettered={dead_lettered_count}, scanned={len(messages)}'
                
            )
        )
