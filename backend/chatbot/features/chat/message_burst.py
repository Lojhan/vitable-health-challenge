import re
from collections.abc import Iterable

FRONTEND_BURST_SEPARATOR_TOKEN = '<USER_MESSAGE_BURST_SEPARATOR>'


def split_incoming_message_payload(raw_message: str) -> list[str]:
    if FRONTEND_BURST_SEPARATOR_TOKEN not in raw_message:
        normalized = raw_message.strip()
        return [normalized] if normalized else []

    parts = [part.strip() for part in raw_message.split(FRONTEND_BURST_SEPARATOR_TOKEN)]
    return [part for part in parts if part]


def build_prompt_from_pending_user_messages(messages: Iterable[object]) -> str:
    messages = list(messages)
    if len(messages) == 1:
        return messages[0].content

    merged = messages[0].content.strip()
    for message in messages[1:]:
        next_piece = message.content.strip()
        if not next_piece:
            continue

        if merged.endswith(('.', '!', '?', ':')):
            merged = f'{merged}\n{next_piece}'
        else:
            merged = f'{merged} {next_piece}'

    return re.sub(r'\s+', ' ', merged).strip()


def is_incomplete_fragment(message: str) -> bool:
    normalized = re.sub(r'\s+', ' ', (message or '').strip().lower())
    if not normalized:
        return True

    connective_tokens = {
        'i', 'im', "i'm", 'have', 'am', 'and', 'but', 'or', 'my', 'the', 'a', 'an',
        'is', 'are', 'was', 'were', 'to', 'of', 'with', 'for', 'it', 'this', 'that',
    }
    punctuation = {'.', '!', '?', ',', ';', ':'}

    if normalized[-1] in punctuation:
        return False

    tokens = normalized.split(' ')
    if all(token in connective_tokens for token in tokens):
        return True

    if len(tokens) == 1 and tokens[0] in connective_tokens:
        return True

    return False


def should_defer_response(pending_user_messages: Iterable[object]) -> bool:
    pending_user_messages = list(pending_user_messages)
    if not pending_user_messages:
        return False

    return all(is_incomplete_fragment(message.content) for message in pending_user_messages)
