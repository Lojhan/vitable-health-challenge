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
from chatbot.features.chat.api.utils import _model_pk
from chatbot.features.chat.composition import (
    build_prepare_chat_turn_use_case,
    build_save_assistant_response_fn,
)
from chatbot.features.chat.sse import single_chunk_response, stream_response_async
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

router = Router()
logger = logging.getLogger(__name__)
obs_logger = StructuredLogger(__name__)

# Keep this alias as a patch seam for tests while sourcing construction from composition.
OpenRouterAgent = build_openrouter_agent


class ChatRequestSchema(Schema):
    message: str
    session_id: int | None = None
    request_id: str | None = None


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
