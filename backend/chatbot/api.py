import asyncio
import re
import threading
import time
from collections.abc import AsyncGenerator
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Iterable
from typing import Any
from typing import cast

from django.contrib.auth import get_user_model
from django.http import StreamingHttpResponse
from ninja import NinjaAPI, Schema
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.tokens import AccessToken

from chatbot.features.ai.base import UserProfileSchema
from chatbot.features.ai.openrouter_agent import OpenRouterAgent
from chatbot.features.chat.models import ChatMessage, ChatSession
from chatbot.features.users.api.auth import router as auth_router


MERGED_IN_PREVIOUS_RESPONSE_TOKEN = '<MERGED_IN_PREVIOUS_RESPONSE>'
FRONTEND_BURST_SEPARATOR_TOKEN = '<USER_MESSAGE_BURST_SEPARATOR>'
CHAT_DEBOUNCE_WINDOW_SECONDS = 1.55
_SESSION_LOCKS: dict[int, threading.Lock] = {}
_SESSION_LOCKS_GUARD = threading.Lock()


class ChatRequestSchema(Schema):
    message: str
    session_id: int | None = None


class ChatMessageResponseSchema(Schema):
    role: str
    content: str
    created_at: str


class ChatSessionResponseSchema(Schema):
    id: int
    title: str
    created_at: str
    updated_at: str
    messages: list[ChatMessageResponseSchema]


class ChatHistoryResponseSchema(Schema):
    sessions: list[ChatSessionResponseSchema]


class ChatHistorySyncSchema(Schema):
    latest_updated_at: str | None
    session_count: int
    message_count: int


api = NinjaAPI()
api.add_router('/auth', auth_router, tags=['Authentication'], auth=None)


def _to_sse_chunk(chunk: str) -> str:
    lines = chunk.splitlines() or ['']
    data_lines = [f'data: {line}' for line in lines]
    return '\n'.join(data_lines) + '\n\n'


def _single_chunk_response(chunk: str) -> Iterable[bytes]:
    return [_to_sse_chunk(chunk).encode()]


def _get_session_lock(session_id: int) -> threading.Lock:
    with _SESSION_LOCKS_GUARD:
        lock = _SESSION_LOCKS.get(session_id)
        if lock is None:
            lock = threading.Lock()
            _SESSION_LOCKS[session_id] = lock
        return lock


def _model_pk(instance: object) -> int:
    return cast(int, cast(Any, instance).pk)


def _stream_async_generator(
    async_generator: AsyncGenerator[str, None],
    on_close: Callable[[], Awaitable[None]] | None = None,
    on_complete: Callable[[Iterable[str]], None] | None = None,
):
    async def collect_chunks() -> list[str]:
        try:
            return [chunk async for chunk in async_generator]
        finally:
            if on_close is not None:
                await on_close()

    chunks = asyncio.run(collect_chunks())

    if on_complete is not None:
        on_complete(chunks)

    for chunk in chunks:
        yield _to_sse_chunk(chunk).encode()


def _get_user_from_jwt(request):
    authorization_header = request.headers.get('Authorization', '')
    if not authorization_header.startswith('Bearer '):
        return None

    token_value = authorization_header.split(' ', maxsplit=1)[1]
    token = AccessToken(token_value)
    user_id = token.get('user_id')

    user_model = get_user_model()
    return user_model.objects.get(id=user_id)


def _get_authenticated_user(request) -> Any:
    user = _get_user_from_jwt(request)
    if user is None:
        raise ValueError('Authenticated user could not be resolved from JWT.')
    return cast(Any, user)


def _get_or_create_chat_session(user, session_id: int | None) -> ChatSession:
    if session_id is not None:
        session = ChatSession.objects.filter(id=session_id, user_id=user.id).first()
        if session is not None:
            return session

    return ChatSession.objects.create(user=user)


def _build_history_for_session(session: ChatSession) -> list[dict[str, str]]:
    return list(
        ChatMessage.objects.filter(session=session).values('role', 'content')
    )


def _split_incoming_message_payload(raw_message: str) -> list[str]:
    if FRONTEND_BURST_SEPARATOR_TOKEN not in raw_message:
        normalized = raw_message.strip()
        return [normalized] if normalized else []

    parts = [
        part.strip()
        for part in raw_message.split(FRONTEND_BURST_SEPARATOR_TOKEN)
    ]
    return [part for part in parts if part]


def _split_history_and_pending_user_messages(
    session: ChatSession,
) -> tuple[list[dict[str, str]], list[ChatMessage]]:
    ordered_messages = list(
        ChatMessage.objects.filter(session=session)
        .only('id', 'role', 'content', 'created_at')
        .order_by('created_at', 'id')
    )

    last_assistant_index = -1
    for index, message in enumerate(ordered_messages):
        if message.role == ChatMessage.ROLE_ASSISTANT:
            last_assistant_index = index

    history_messages = ordered_messages[: last_assistant_index + 1]
    pending_user_messages = [
        message
        for message in ordered_messages[last_assistant_index + 1 :]
        if message.role == ChatMessage.ROLE_USER
    ]

    history_payload = [
        {'role': message.role, 'content': message.content}
        for message in history_messages
    ]
    return history_payload, pending_user_messages


def _build_prompt_from_pending_user_messages(messages: list[ChatMessage]) -> str:
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


def _is_incomplete_fragment(message: str) -> bool:
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


def _should_defer_response(pending_user_messages: list[ChatMessage]) -> bool:
    if not pending_user_messages:
        return False

    return all(_is_incomplete_fragment(message.content) for message in pending_user_messages)


def _build_session_title(session: ChatSession) -> str:
    first_user_message = ChatMessage.objects.filter(
        session=session,
        role=ChatMessage.ROLE_USER,
    ).order_by('created_at', 'id').values_list('content', flat=True).first()

    if not first_user_message:
        return 'New conversation'

    normalized = ' '.join(first_user_message.split())
    if not normalized:
        return 'New conversation'

    return normalized[:42]


@api.post('/chat', auth=JWTAuth())
def post_chat(request, payload: ChatRequestSchema):
    user = _get_authenticated_user(request)
    session = _get_or_create_chat_session(user=user, session_id=payload.session_id)
    incoming_messages = _split_incoming_message_payload(payload.message)
    if not incoming_messages:
        incoming_messages = [payload.message.strip() or payload.message]

    created_messages = [
        ChatMessage.objects.create(
            session=session,
            role=ChatMessage.ROLE_USER,
            content=message,
        )
        for message in incoming_messages
    ]
    request_message = created_messages[-1]

    session_lock = _get_session_lock(_model_pk(session))
    with session_lock:
        if CHAT_DEBOUNCE_WINDOW_SECONDS > 0:
            time.sleep(CHAT_DEBOUNCE_WINDOW_SECONDS)

        history, pending_user_messages = _split_history_and_pending_user_messages(session)

        if _should_defer_response(pending_user_messages):
            response = StreamingHttpResponse(
                _single_chunk_response(MERGED_IN_PREVIOUS_RESPONSE_TOKEN),
                content_type='text/event-stream',
            )
            response['X-Chat-Session-Id'] = str(_model_pk(session))
            return response

        if _model_pk(request_message) not in {_model_pk(message) for message in pending_user_messages}:
            response = StreamingHttpResponse(
                _single_chunk_response(MERGED_IN_PREVIOUS_RESPONSE_TOKEN),
                content_type='text/event-stream',
            )
            response['X-Chat-Session-Id'] = str(_model_pk(session))
            return response

        prompt_for_agent = _build_prompt_from_pending_user_messages(
            pending_user_messages,
        )

        user_profile = UserProfileSchema(
            first_name=user.first_name,
            insurance_tier=user.insurance_tier,
        )
        agent = OpenRouterAgent(user_profile=user_profile, user_id=cast(int, user.id))
        close_callback = getattr(agent, 'aclose', None)
        on_close = (
            cast(Callable[[], Awaitable[None]], close_callback)
            if callable(close_callback)
            else None
        )

        def save_assistant_message(chunks: Iterable[str]) -> None:
            response_content = ''.join(chunks)
            if not response_content:
                return

            ChatMessage.objects.create(
                session=session,
                role=ChatMessage.ROLE_ASSISTANT,
                content=response_content,
            )

        response = StreamingHttpResponse(
            _stream_async_generator(
                agent.stream_response(
                    prompt_for_agent,
                    history=history,
                ),
                on_close=on_close,
                on_complete=save_assistant_message,
            ),
            content_type='text/event-stream',
        )
        response['X-Chat-Session-Id'] = str(_model_pk(session))

        return response


@api.get('/chat/history', auth=JWTAuth(), response=ChatHistoryResponseSchema)
def get_chat_history(request):
    user = _get_authenticated_user(request)
    sessions = (
        ChatSession.objects.filter(user_id=user.id)
        .prefetch_related('messages')
        .order_by('-updated_at', '-id')
    )

    payload_sessions = []
    for session in sessions:
        payload_sessions.append(
            {
                'id': _model_pk(session),
                'title': _build_session_title(session),
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat(),
                'messages': [
                    {
                        'role': message.role,
                        'content': message.content,
                        'created_at': message.created_at.isoformat(),
                    }
                    for message in ChatMessage.objects.filter(session=session).order_by('created_at', 'id')
                ],
            }
        )

    return {'sessions': payload_sessions}


@api.get('/chat/history-sync', auth=JWTAuth(), response=ChatHistorySyncSchema)
def get_chat_history_sync(request):
    user = _get_authenticated_user(request)
    sessions = ChatSession.objects.filter(user_id=user.id)
    latest_updated_at = sessions.values_list('updated_at', flat=True).first()
    message_count = ChatMessage.objects.filter(session__user_id=user.id).count()

    return {
        'latest_updated_at': (
            latest_updated_at.isoformat() if latest_updated_at is not None else None
        ),
        'session_count': sessions.count(),
        'message_count': message_count,
    }


@api.delete('/chat/sessions/{session_id}', auth=JWTAuth())
def delete_chat_session(request, session_id: int):
    user = _get_authenticated_user(request)
    deleted_count, _ = ChatSession.objects.filter(
        id=session_id,
        user_id=user.id,
    ).delete()

    return {'deleted': deleted_count > 0}
