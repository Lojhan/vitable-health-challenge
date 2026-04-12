import logging
from collections.abc import Awaitable, Callable
from typing import Any, cast
from uuid import uuid4

from asgiref.sync import sync_to_async
from django.http import StreamingHttpResponse
from ninja import Router, Schema
from ninja.responses import Status
from ninja_jwt.authentication import JWTAuth

from chatbot.features.ai.composition import build_openrouter_agent, build_user_profile
from chatbot.features.chat.composition import (
    build_delete_chat_session_use_case,
    build_get_chat_history_sync_use_case,
    build_get_chat_history_use_case,
    build_prepare_chat_turn_use_case,
    build_save_assistant_response_fn,
)
from chatbot.features.chat.sse import single_chunk_response, stream_async_generator, stream_response_async
from chatbot.features.core.api.validation import to_validation_status
from chatbot.features.core.auth_context import get_authenticated_user
from chatbot.features.core.domain.validation import DomainValidationError
from chatbot.features.core.observability import (
    StructuredLogger,
    TimingContext,
    clear_context,
    set_request_id,
    set_user_id,
)

MERGED_IN_PREVIOUS_RESPONSE_TOKEN = '<MERGED_IN_PREVIOUS_RESPONSE>'
CHAT_DEBOUNCE_WINDOW_SECONDS = 1.55
logger = logging.getLogger(__name__)
obs_logger = StructuredLogger(__name__)

router = Router()

# Keep this alias as a patch seam for tests while sourcing construction from composition.
OpenRouterAgent = build_openrouter_agent


class ChatRequestSchema(Schema):
    message: str
    session_id: int | None = None
    request_id: str | None = None


class ChatMessageResponseSchema(Schema):
    role: str
    message_kind: str
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


def _model_pk(instance: object) -> int:
    return cast(int, cast(Any, instance).pk)


def _build_session_title(session: Any) -> str:
    prefetched_messages = getattr(session, '_prefetched_objects_cache', {}).get('messages')
    if prefetched_messages is not None:
        first_user_message = next(
            (
                message.content
                for message in sorted(
                    prefetched_messages,
                    key=lambda message: (message.created_at, message.id),
                )
                if message.role == 'user'
            ),
            None,
        )
    else:
        first_user_message = None

    if not first_user_message:
        return 'New conversation'

    normalized = ' '.join(first_user_message.split())
    if not normalized:
        return 'New conversation'

    return normalized[:42]


def _serialize_chat_session(session: Any) -> dict[str, object]:
    prefetched_messages = getattr(session, '_prefetched_objects_cache', {}).get('messages')
    if prefetched_messages is not None:
        ordered_messages = sorted(
            prefetched_messages,
            key=lambda message: (message.created_at, message.id),
        )
    else:
        ordered_messages = []

    return {
        'id': _model_pk(session),
        'title': _build_session_title(session),
        'created_at': session.created_at.isoformat(),
        'updated_at': session.updated_at.isoformat(),
        'messages': [
            {
                'role': message.role,
                'message_kind': message.message_kind,
                'content': message.content,
                'created_at': message.created_at.isoformat(),
            }
            for message in ordered_messages
        ],
    }


@router.post('/chat', auth=JWTAuth())
async def post_chat(request: Any, payload: ChatRequestSchema) -> StreamingHttpResponse | Status:
    request_id = payload.request_id or str(uuid4())
    user = await sync_to_async(get_authenticated_user, thread_sensitive=True)(request)
    prepared_turn: Any | None = None
    agent: Any | None = None
    
    # Set correlation IDs in context for this request
    set_request_id(request_id)
    set_user_id(cast(int, user.id))
    
    try:
        with TimingContext('chat.turn.preparation'):
            prepared_turn = await sync_to_async(
                build_prepare_chat_turn_use_case(
                    debounce_window_seconds=CHAT_DEBOUNCE_WINDOW_SECONDS,
                ).execute,
                thread_sensitive=True,
            )(
                user=user,
                message=payload.message,
                session_id=payload.session_id,
                request_id=payload.request_id,
            )
    except DomainValidationError as error:
        obs_logger.warning(
            'chat.turn.validation_failed',
            reason_code='DOMAIN_VALIDATION_ERROR',
            details={'error': str(error)},
        )
        return to_validation_status(error)

    assert prepared_turn is not None

    obs_logger.info(
        'chat.turn.prepared',
        details={
            'session_id': _model_pk(prepared_turn.session),
            'merged_into_previous': prepared_turn.merged_into_previous_response,
        },
    )

    if prepared_turn.merged_into_previous_response:
        response = StreamingHttpResponse(
            single_chunk_response(MERGED_IN_PREVIOUS_RESPONSE_TOKEN),
            content_type='text/event-stream',
        )
        response['X-Chat-Session-Id'] = str(_model_pk(prepared_turn.session))
        response['X-Request-Id'] = request_id
        clear_context()
        return response

    user_profile = build_user_profile(
        first_name=user.first_name,
        insurance_tier=user.insurance_tier,
    )

    with TimingContext('chat.agent_initialization'):
        agent = OpenRouterAgent(
            user_profile=user_profile,
            user_id=cast(int, user.id),
        )

    assert agent is not None
    
    close_callback = getattr(agent, 'aclose', None)
    on_close = (
        cast(Callable[[], Awaitable[None]], close_callback)
        if callable(close_callback)
        else None
    )

    save_assistant_message = build_save_assistant_response_fn(session=prepared_turn.session)

    response = StreamingHttpResponse(
        stream_response_async(
            agent.stream_response(
                cast(str, prepared_turn.prompt_for_agent),
                history=prepared_turn.history,
            ),
            on_close=on_close,
            on_complete=save_assistant_message,
        ),
        content_type='text/event-stream',
    )
    response['X-Chat-Session-Id'] = str(_model_pk(prepared_turn.session))
    response['X-Request-Id'] = request_id
    response['Cache-Control'] = 'no-cache, no-transform'
    response['X-Accel-Buffering'] = 'no'

    return response


@router.get('/chat/history', auth=JWTAuth(), response=ChatHistoryResponseSchema)
def get_chat_history(request: Any) -> dict[str, object]:
    user = get_authenticated_user(request)
    return build_get_chat_history_use_case(
        serialize_session=_serialize_chat_session,
    ).execute(
        user_id=cast(int, user.id),
    )


@router.get('/chat/history-sync', auth=JWTAuth(), response=ChatHistorySyncSchema)
def get_chat_history_sync(request: Any) -> dict[str, object]:
    user = get_authenticated_user(request)
    return build_get_chat_history_sync_use_case().execute(user_id=cast(int, user.id))


@router.delete('/chat/sessions/{session_id}', auth=JWTAuth())
def delete_chat_session(request: Any, session_id: int) -> dict[str, bool]:
    user = get_authenticated_user(request)
    deleted = build_delete_chat_session_use_case().execute(
        user_id=cast(int, user.id),
        session_id=session_id,
    )

    return {'deleted': deleted}


# ── Structured interaction selection persistence ──────────────────────────────

class StructuredInteractionSaveSchema(Schema):
    interaction_id: str
    kind: str
    selection: dict[str, Any]


class StructuredInteractionResponseSchema(Schema):
    interaction_id: str
    selection: dict[str, Any] | None


@router.get(
    '/chat/structured-interactions/{interaction_id}',
    auth=JWTAuth(),
    response=StructuredInteractionResponseSchema,
)
def get_structured_interaction(request: Any, interaction_id: str) -> dict[str, object]:
    from chatbot.features.chat.models import StructuredInteraction

    user = get_authenticated_user(request)
    normalized_id = interaction_id.strip()
    if not normalized_id:
        return {'interaction_id': '', 'selection': None}

    row = StructuredInteraction.objects.filter(
        user_id=cast(int, user.id),
        interaction_id=normalized_id,
    ).first()

    return {
        'interaction_id': normalized_id,
        'selection': row.selection if row else None,
    }


@router.post(
    '/chat/structured-interactions',
    auth=JWTAuth(),
    response=StructuredInteractionResponseSchema,
)
def save_structured_interaction(
    request: Any,
    payload: StructuredInteractionSaveSchema,
) -> dict[str, object]:
    from chatbot.features.chat.models import StructuredInteraction

    user = get_authenticated_user(request)
    normalized_id = payload.interaction_id.strip()
    if not normalized_id or not payload.selection:
        return {'interaction_id': normalized_id, 'selection': None}

    selection_data = {
        'kind': payload.kind,
        **payload.selection,
        'saved_at': __import__('django').utils.timezone.now().isoformat(),
    }

    row, created = StructuredInteraction.objects.update_or_create(
        user_id=cast(int, user.id),
        interaction_id=normalized_id,
        defaults={
            'kind': payload.kind,
            'selection': selection_data,
        },
    )

    return {
        'interaction_id': normalized_id,
        'selection': row.selection,
    }
