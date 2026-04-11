from collections.abc import Callable

from chatbot.features.core.models import OutboxMessage

OutboxHandler = Callable[[OutboxMessage], None]


def _noop_handler(_message: OutboxMessage) -> None:
    return None


HANDLERS: dict[str, OutboxHandler] = {
    'users.user_signed_up': _noop_handler,
}


def dispatch_outbox_message(message: OutboxMessage) -> None:
    handler = HANDLERS.get(message.event_type, _noop_handler)
    handler(message)
