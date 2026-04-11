import inspect

import pytest
from django.contrib.auth import get_user_model

from chatbot.features.chat.application.use_cases import (
    DeleteChatSessionUseCase,
    PrepareChatTurnUseCase,
)
from chatbot.features.chat.application.use_cases.prepare_chat_turn import _ROLE_USER
from chatbot.features.chat.infrastructure.unit_of_work.django_chat import DjangoChatUnitOfWork
from chatbot.features.chat.models import ChatMessage, ChatSession


@pytest.mark.django_db
def test_prepare_chat_turn_use_case_creates_session_and_prompt_when_message_is_actionable():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='chat-usecase-user',
        password='safe-password-123',
        first_name='Casey',
        insurance_tier='Silver',
        medical_history={},
    )

    prepared = PrepareChatTurnUseCase(debounce_window_seconds=0, uow=DjangoChatUnitOfWork()).execute(
        user=user,
        message='I have fever',
        session_id=None,
    )

    assert prepared.merged_into_previous_response is False
    assert prepared.prompt_for_agent == 'I have fever'
    assert prepared.history == []
    assert ChatSession.objects.filter(id=prepared.session.id, user_id=user.id).exists()


@pytest.mark.django_db
def test_prepare_chat_turn_use_case_defers_for_fragment_only_pending_messages():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='chat-fragment-user',
        password='safe-password-123',
        first_name='Casey',
        insurance_tier='Silver',
        medical_history={},
    )
    session = ChatSession.objects.create(user=user)

    ChatMessage.objects.create(
        session=session,
        role=ChatMessage.ROLE_USER,
        content='i',
    )

    prepared = PrepareChatTurnUseCase(debounce_window_seconds=0, uow=DjangoChatUnitOfWork()).execute(
        user=user,
        message='have',
        session_id=session.id,
    )

    assert prepared.merged_into_previous_response is True
    assert prepared.prompt_for_agent is None


@pytest.mark.django_db
def test_delete_chat_session_use_case_only_deletes_owned_session():
    user_model = get_user_model()
    owner = user_model.objects.create_user(
        username='chat-delete-owner',
        password='safe-password-123',
        first_name='Owner',
        insurance_tier='Silver',
        medical_history={},
    )
    outsider = user_model.objects.create_user(
        username='chat-delete-outsider',
        password='safe-password-123',
        first_name='Outsider',
        insurance_tier='Bronze',
        medical_history={},
    )
    session = ChatSession.objects.create(user=owner)

    use_case = DeleteChatSessionUseCase(uow=DjangoChatUnitOfWork())

    assert use_case.execute(user_id=outsider.id, session_id=session.id) is False
    assert ChatSession.objects.filter(id=session.id).exists() is True

    assert use_case.execute(user_id=owner.id, session_id=session.id) is True
    assert ChatSession.objects.filter(id=session.id).exists() is False


@pytest.mark.django_db(transaction=True)
def test_prepare_chat_turn_is_idempotent_with_same_request_id():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='chat-idempotency-user',
        password='safe-password-123',
        first_name='Casey',
        insurance_tier='Silver',
        medical_history={},
    )

    use_case = PrepareChatTurnUseCase(
        debounce_window_seconds=0,
        uow=DjangoChatUnitOfWork(),
    )
    first_turn = use_case.execute(
        user=user,
        message='I have fever',
        session_id=None,
        request_id='same-request-id',
    )
    second_turn = use_case.execute(
        user=user,
        message='I have fever',
        session_id=first_turn.session.id,
        request_id='same-request-id',
    )

    assert first_turn.merged_into_previous_response is False
    assert second_turn.merged_into_previous_response is True
    assert (
        ChatMessage.objects.filter(
            session_id=first_turn.session.id,
            role=_ROLE_USER,
            request_id='same-request-id',
        ).count()
        == 1
    )


def test_prepare_chat_turn_has_no_process_local_session_lock_registry():
    source = inspect.getsource(PrepareChatTurnUseCase)
    assert '_SESSION_LOCKS' not in source
    assert 'threading.Lock' not in source


@pytest.mark.django_db
def test_chat_message_defaults_to_text_message_kind():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='chat-message-kind-user',
        password='safe-password-123',
        first_name='Casey',
        insurance_tier='Silver',
        medical_history={},
    )
    session = ChatSession.objects.create(user=user)

    message = ChatMessage.objects.create(
        session=session,
        role=ChatMessage.ROLE_USER,
        content='Need help',
    )

    assert message.message_kind == ChatMessage.MessageKind.TEXT
