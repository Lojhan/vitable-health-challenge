import os
import threading
import time
from collections.abc import Iterable
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.http import StreamingHttpResponse
from django.test import Client

from chatbot.api import _stream_async_generator
from chatbot.api import _to_sse_chunk
from chatbot.api import FRONTEND_BURST_SEPARATOR_TOKEN
from chatbot.api import MERGED_IN_PREVIOUS_RESPONSE_TOKEN
from chatbot.features.chat.models import ChatMessage
from chatbot.features.chat.models import ChatSession
from chatbot.features.scheduling.models import Appointment
from chatbot.features.scheduling.tools import book_appointment
from chatbot.features.scheduling.tools import list_user_appointments


def _pk(instance: object) -> int:
    return cast(int, cast(Any, instance).pk)


def _user_id(appointment: Appointment) -> int:
    return cast(int, cast(Any, appointment).user_id)


def _streaming_body(response: StreamingHttpResponse) -> str:
    return b''.join(cast(Iterable[bytes], response.streaming_content)).decode()


@pytest.mark.django_db
def test_post_api_chat_unauthenticated_returns_401(client):
    response = client.post(
        '/api/chat',
        data={'message': 'hello'},
        content_type='application/json',
    )

    assert response.status_code == 401


@pytest.mark.django_db(transaction=True)
def test_post_api_chat_authenticated_persists_session_history(client, monkeypatch):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='chat-user',
        password='safe-password-123',
        first_name='Jordan',
        insurance_tier='Silver',
        medical_history={},
    )

    class FakeAgent:
        injected_profile = None
        injected_histories = []
        injected_user_id = None

        def __init__(self, user_profile, user_id, **_kwargs):
            FakeAgent.injected_profile = user_profile
            FakeAgent.injected_user_id = user_id

        async def stream_response(self, prompt: str, history=None):
            FakeAgent.injected_histories.append(history or [])
            if prompt == 'hello':
                yield 'chunk-1'
                yield 'chunk-2'
                return

            yield 'follow-up'

    monkeypatch.setattr('chatbot.api.OpenRouterAgent', FakeAgent)

    token_response = client.post(
        '/api/auth/token',
        data={'username': 'chat-user', 'password': 'safe-password-123'},
        content_type='application/json',
    )
    access = token_response.json()['access']

    first_response = client.post(
        '/api/chat',
        data={'message': 'hello'},
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {access}',
    )

    assert first_response.status_code == 200
    assert isinstance(first_response, StreamingHttpResponse)
    assert first_response['Content-Type'] == 'text/event-stream'

    first_streamed = _streaming_body(first_response)
    assert first_streamed == 'data: chunk-1\n\ndata: chunk-2\n\n'

    session_id = int(first_response['X-Chat-Session-Id'])

    second_response = client.post(
        '/api/chat',
        data={'message': 'need another answer', 'session_id': session_id},
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {access}',
    )

    assert second_response.status_code == 200
    second_streamed = _streaming_body(second_response)
    assert second_streamed == 'data: follow-up\n\n'
    assert int(second_response['X-Chat-Session-Id']) == session_id

    assert FakeAgent.injected_profile is not None
    assert FakeAgent.injected_profile.first_name == user.first_name
    assert FakeAgent.injected_profile.insurance_tier == cast(str, cast(Any, user).insurance_tier)
    assert FakeAgent.injected_user_id == _pk(user)
    assert FakeAgent.injected_histories[0] == []
    assert FakeAgent.injected_histories[1] == [
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'chunk-1chunk-2'},
    ]

    stored_messages = list(
        ChatMessage.objects.filter(session_id=session_id).values('role', 'content')
    )
    assert stored_messages == [
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'chunk-1chunk-2'},
        {'role': 'user', 'content': 'need another answer'},
        {'role': 'assistant', 'content': 'follow-up'},
    ]


def test_sse_chunk_mapping_format():
    assert _to_sse_chunk('hello') == 'data: hello\n\n'


def test_sse_chunk_mapping_format_multiline_content():
    assert _to_sse_chunk('line 1\nline 2') == 'data: line 1\ndata: line 2\n\n'


@pytest.mark.django_db(transaction=True)
def test_post_api_chat_splits_separator_token_into_individual_user_messages(client, monkeypatch):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='split-user',
        password='safe-password-123',
        first_name='Jordan',
        insurance_tier='Silver',
        medical_history={},
    )

    class FakeAgent:
        seen_prompts = []

        def __init__(self, **_kwargs):
            pass

        async def stream_response(self, prompt: str, history=None):
            FakeAgent.seen_prompts.append(prompt)
            yield 'token-split-ok'

    monkeypatch.setattr('chatbot.api.OpenRouterAgent', FakeAgent)
    monkeypatch.setattr('chatbot.api.CHAT_DEBOUNCE_WINDOW_SECONDS', 0)

    token_response = client.post(
        '/api/auth/token',
        data={'username': 'split-user', 'password': 'safe-password-123'},
        content_type='application/json',
    )
    access = token_response.json()['access']

    payload_message = FRONTEND_BURST_SEPARATOR_TOKEN.join(['i', 'have', 'fever'])
    response = client.post(
        '/api/chat',
        data={'message': payload_message},
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {access}',
    )

    assert response.status_code == 200
    streamed = _streaming_body(response)
    assert streamed == 'data: token-split-ok\n\n'

    assert FakeAgent.seen_prompts == ['i have fever']

    session_id = int(response['X-Chat-Session-Id'])
    stored_messages = list(
        ChatMessage.objects.filter(session_id=session_id).values('role', 'content')
    )
    assert stored_messages == [
        {'role': 'user', 'content': 'i'},
        {'role': 'user', 'content': 'have'},
        {'role': 'user', 'content': 'fever'},
        {'role': 'assistant', 'content': 'token-split-ok'},
    ]


def test_stream_async_generator_runs_on_close_callback_and_collects_chunks():
    close_called = False
    collected_chunks = []

    async def generator():
        yield 'hello'

    async def on_close():
        nonlocal close_called
        close_called = True

    def on_complete(chunks):
        collected_chunks.extend(chunks)

    streamed = b''.join(
        _stream_async_generator(
            generator(),
            on_close=on_close,
            on_complete=on_complete,
        )
    ).decode()

    assert streamed == 'data: hello\n\n'
    assert close_called is True
    assert collected_chunks == ['hello']


@pytest.mark.django_db(transaction=True)
def test_post_api_chat_long_conversation_keeps_full_context(client, monkeypatch):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='long-chat-user',
        password='safe-password-123',
        first_name='Vinicius',
        insurance_tier='Gold',
        medical_history={},
    )

    class FakeAgent:
        seen_histories = []
        seen_prompts = []
        booked_appointment_id = None

        def __init__(self, user_id, **_kwargs):
            self.user_id = user_id

        @staticmethod
        def _last_user_message_containing(history, text):
            for item in reversed(history):
                if item['role'] == 'user' and text in item['content'].lower():
                    return item['content']
            return None

        async def stream_response(self, prompt: str, history=None):
            history = history or []
            prompt_lower = prompt.lower()

            FakeAgent.seen_prompts.append(prompt)
            FakeAgent.seen_histories.append(history)

            if 'sore throat' in prompt_lower and 'fever' not in prompt_lower:
                yield (
                    'I am sorry you are feeling unwell. Do you have fever, cough, '
                    'or any trouble swallowing?'
                )
                return

            if 'fever and cough' in prompt_lower:
                yield (
                    'Thanks for the details. I can help schedule a visit. '
                    'Please share a brief symptom summary and appointment reason.'
                )
                return

            if 'schedule something next monday' in prompt_lower:
                yield (
                    'Understood. Before booking, please confirm symptoms summary '
                    'and reason for the appointment.'
                )
                return

            if 'sore throat, fever and cough' in prompt_lower:
                yield (
                    'Thanks, I captured your symptoms and reason. '
                    'Please confirm if I should book next Monday at 9:00 AM UTC.'
                )
                return

            if prompt_lower.strip() == 'yes, next monday':
                symptom_line = self._last_user_message_containing(
                    history,
                    'sore throat, fever and cough',
                )
                if symptom_line is None:
                    yield 'I am missing your symptom context. Please summarize symptoms first.'
                    return

                previous_async_unsafe = os.environ.get('DJANGO_ALLOW_ASYNC_UNSAFE')
                os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
                try:
                    appointment = book_appointment(
                        user_id=self.user_id,
                        time_slot='next monday 09:00',
                        symptoms_summary='sore throat, fever and cough',
                        appointment_reason=symptom_line,
                    )
                finally:
                    if previous_async_unsafe is None:
                        del os.environ['DJANGO_ALLOW_ASYNC_UNSAFE']
                    else:
                        os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = previous_async_unsafe
                FakeAgent.booked_appointment_id = _pk(appointment)
                yield (
                    f'Appointment booked for next Monday at 9:00 AM UTC. '
                    f'Appointment ID: {_pk(appointment)}.'
                )
                return

            if 'what are my future appointments' in prompt_lower:
                previous_async_unsafe = os.environ.get('DJANGO_ALLOW_ASYNC_UNSAFE')
                os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
                try:
                    payload = list_user_appointments(user_id=self.user_id)
                finally:
                    if previous_async_unsafe is None:
                        del os.environ['DJANGO_ALLOW_ASYNC_UNSAFE']
                    else:
                        os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = previous_async_unsafe
                if payload['count'] == 0:
                    yield payload['summary']
                    return

                formatted = ' '.join(payload['formatted_lines'])
                yield f"{payload['summary']} {formatted}"
                return

            yield 'Could you rephrase that so I can help?'

    monkeypatch.setattr('chatbot.api.OpenRouterAgent', FakeAgent)

    token_response = client.post(
        '/api/auth/token',
        data={'username': 'long-chat-user', 'password': 'safe-password-123'},
        content_type='application/json',
    )
    access = token_response.json()['access']

    prompts = [
        'hello :(',
        'I have a sore throat',
        'yes, I have fever and cough',
        'can I schedule something next monday?',
        'sore throat, fever and cough, thats also the reason',
        'yes, next monday',
    ]

    session_id = None
    streamed_responses = []

    for index, prompt in enumerate(prompts):
        payload: dict[str, str | int] = {'message': prompt}
        if session_id is not None:
            payload['session_id'] = session_id

        response = client.post(
            '/api/chat',
            data=payload,
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {access}',
        )

        assert response.status_code == 200
        streamed = _streaming_body(response)
        assert streamed.startswith('data: ')
        assert streamed.endswith('\n\n')

        current_session_id = int(response['X-Chat-Session-Id'])
        if session_id is None:
            session_id = current_session_id
        else:
            assert current_session_id == session_id

        streamed_responses.append(streamed.removeprefix('data: ').strip())

    assert FakeAgent.seen_prompts == prompts
    assert len(FakeAgent.seen_histories) == len(prompts)

    for index, history in enumerate(FakeAgent.seen_histories):
        expected_history_length = index * 2
        assert len(history) == expected_history_length

        if index == 0:
            continue

        previous_prompt = prompts[index - 1]
        previous_response = streamed_responses[index - 1]
        assert history[-2] == {'role': 'user', 'content': previous_prompt}
        assert history[-1] == {'role': 'assistant', 'content': previous_response}

    stored_messages = list(
        ChatMessage.objects.filter(session_id=session_id).values('role', 'content')
    )
    assert len(stored_messages) == len(prompts) * 2

    for index, prompt in enumerate(prompts):
        assert stored_messages[(index * 2)] == {'role': 'user', 'content': prompt}
        assert stored_messages[(index * 2) + 1] == {
            'role': 'assistant',
            'content': streamed_responses[index],
        }

    assert FakeAgent.booked_appointment_id is not None
    appointment = Appointment.objects.get(id=FakeAgent.booked_appointment_id)
    assert _user_id(appointment) == _pk(user)
    assert appointment.symptoms_summary == 'sore throat, fever and cough'
    assert 'thats also the reason' in appointment.appointment_reason

    new_session_response = client.post(
        '/api/chat',
        data={'message': 'what are my future appointments?'},
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {access}',
    )

    assert new_session_response.status_code == 200
    assert int(new_session_response['X-Chat-Session-Id']) != session_id

    listing_streamed = _streaming_body(new_session_response)
    assert 'You have 1 upcoming appointment(s).' in listing_streamed
    assert f'Appointment #{_pk(appointment)}:' in listing_streamed
    assert 'Symptoms: sore throat, fever and cough' in listing_streamed


@pytest.mark.django_db
def test_get_chat_history_and_sync_authenticated(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='history-user',
        password='safe-password-123',
        first_name='Casey',
        insurance_tier='Silver',
        medical_history={},
    )
    session = ChatSession.objects.create(user=user)
    ChatMessage.objects.create(session=session, role='user', content='severe headache')
    ChatMessage.objects.create(session=session, role='assistant', content='please hydrate')

    token_response = client.post(
        '/api/auth/token',
        data={'username': 'history-user', 'password': 'safe-password-123'},
        content_type='application/json',
    )
    access = token_response.json()['access']

    history_response = client.get(
        '/api/chat/history',
        HTTP_AUTHORIZATION=f'Bearer {access}',
    )
    assert history_response.status_code == 200
    payload = history_response.json()
    assert len(payload['sessions']) == 1
    assert payload['sessions'][0]['id'] == _pk(session)
    assert payload['sessions'][0]['title'] == 'severe headache'
    assert payload['sessions'][0]['messages'] == [
        {
            'role': 'user',
            'content': 'severe headache',
            'created_at': payload['sessions'][0]['messages'][0]['created_at'],
        },
        {
            'role': 'assistant',
            'content': 'please hydrate',
            'created_at': payload['sessions'][0]['messages'][1]['created_at'],
        },
    ]

    sync_response = client.get(
        '/api/chat/history-sync',
        HTTP_AUTHORIZATION=f'Bearer {access}',
    )
    assert sync_response.status_code == 200
    sync_payload = sync_response.json()
    assert sync_payload['session_count'] == 1
    assert sync_payload['message_count'] == 2
    assert sync_payload['latest_updated_at'] is not None


@pytest.mark.django_db
def test_delete_chat_session_only_for_owner(client):
    user_model = get_user_model()
    owner = user_model.objects.create_user(
        username='owner-user',
        password='safe-password-123',
        first_name='Owner',
        insurance_tier='Silver',
        medical_history={},
    )
    outsider = user_model.objects.create_user(
        username='outsider-user',
        password='safe-password-123',
        first_name='Outsider',
        insurance_tier='Bronze',
        medical_history={},
    )
    session = ChatSession.objects.create(user=owner)

    owner_token_response = client.post(
        '/api/auth/token',
        data={'username': 'owner-user', 'password': 'safe-password-123'},
        content_type='application/json',
    )
    owner_access = owner_token_response.json()['access']

    outsider_token_response = client.post(
        '/api/auth/token',
        data={'username': 'outsider-user', 'password': 'safe-password-123'},
        content_type='application/json',
    )
    outsider_access = outsider_token_response.json()['access']

    outsider_delete_response = client.delete(
        f'/api/chat/sessions/{_pk(session)}',
        HTTP_AUTHORIZATION=f'Bearer {outsider_access}',
    )
    assert outsider_delete_response.status_code == 200
    assert outsider_delete_response.json() == {'deleted': False}
    assert ChatSession.objects.filter(id=_pk(session)).exists() is True

    owner_delete_response = client.delete(
        f'/api/chat/sessions/{_pk(session)}',
        HTTP_AUTHORIZATION=f'Bearer {owner_access}',
    )
    assert owner_delete_response.status_code == 200
    assert owner_delete_response.json() == {'deleted': True}
    assert ChatSession.objects.filter(id=_pk(session)).exists() is False


@pytest.mark.django_db(transaction=True)
def test_post_api_chat_debounce_merges_quick_successive_messages(client, monkeypatch):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='debounce-user',
        password='safe-password-123',
        first_name='Deb',
        insurance_tier='Silver',
        medical_history={},
    )

    class FakeAgent:
        seen_prompts = []

        def __init__(self, **_kwargs):
            pass

        async def stream_response(self, prompt: str, history=None):
            FakeAgent.seen_prompts.append(prompt)
            yield 'debounced-assistant-response'

    monkeypatch.setattr('chatbot.api.OpenRouterAgent', FakeAgent)
    monkeypatch.setattr('chatbot.api.CHAT_DEBOUNCE_WINDOW_SECONDS', 0.2)

    token_response = client.post(
        '/api/auth/token',
        data={'username': 'debounce-user', 'password': 'safe-password-123'},
        content_type='application/json',
    )
    access = token_response.json()['access']

    initial_response = client.post(
        '/api/chat',
        data={'message': 'starting context'},
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {access}',
    )
    assert initial_response.status_code == 200
    _ = _streaming_body(initial_response)
    session_id = int(initial_response['X-Chat-Session-Id'])

    streamed_by_request = {}

    def send_in_thread(key: str, message: str) -> None:
        thread_client = Client()
        response = thread_client.post(
            '/api/chat',
            data={'message': message, 'session_id': session_id},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {access}',
        )
        assert isinstance(response, StreamingHttpResponse)
        streamed_by_request[key] = _streaming_body(response)

    first_thread = threading.Thread(
        target=send_in_thread,
        args=('first', 'first follow-up detail'),
    )
    second_thread = threading.Thread(
        target=send_in_thread,
        args=('second', 'second follow-up detail'),
    )

    first_thread.start()
    time.sleep(0.05)
    second_thread.start()
    first_thread.join()
    second_thread.join()

    streamed_payloads = list(streamed_by_request.values())
    assert len(streamed_payloads) == 2
    assert 'data: debounced-assistant-response\n\n' in streamed_payloads
    assert f'data: {MERGED_IN_PREVIOUS_RESPONSE_TOKEN}\n\n' in streamed_payloads

    assert len(FakeAgent.seen_prompts) == 2
    merged_prompt = FakeAgent.seen_prompts[1]
    assert merged_prompt == 'first follow-up detail second follow-up detail'

    stored_messages = list(
        ChatMessage.objects.filter(session_id=session_id).values('role', 'content')
    )
    assert stored_messages == [
        {'role': 'user', 'content': 'starting context'},
        {'role': 'assistant', 'content': 'debounced-assistant-response'},
        {'role': 'user', 'content': 'first follow-up detail'},
        {'role': 'user', 'content': 'second follow-up detail'},
        {'role': 'assistant', 'content': 'debounced-assistant-response'},
    ]


@pytest.mark.django_db(transaction=True)
def test_post_api_chat_defers_connective_fragments_until_meaningful_message(client, monkeypatch):
    user_model = get_user_model()
    user_model.objects.create_user(
        username='fragment-user',
        password='safe-password-123',
        first_name='Frag',
        insurance_tier='Silver',
        medical_history={},
    )

    class FakeAgent:
        seen_prompts = []

        def __init__(self, **_kwargs):
            pass

        async def stream_response(self, prompt: str, history=None):
            FakeAgent.seen_prompts.append(prompt)
            yield 'fragment-merged-response'

    monkeypatch.setattr('chatbot.api.OpenRouterAgent', FakeAgent)
    monkeypatch.setattr('chatbot.api.CHAT_DEBOUNCE_WINDOW_SECONDS', 0)

    token_response = client.post(
        '/api/auth/token',
        data={'username': 'fragment-user', 'password': 'safe-password-123'},
        content_type='application/json',
    )
    access = token_response.json()['access']

    first_response = client.post(
        '/api/chat',
        data={'message': 'i'},
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {access}',
    )
    first_streamed = _streaming_body(first_response)
    assert first_streamed == f'data: {MERGED_IN_PREVIOUS_RESPONSE_TOKEN}\n\n'
    session_id = int(first_response['X-Chat-Session-Id'])

    second_response = client.post(
        '/api/chat',
        data={'message': 'have', 'session_id': session_id},
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {access}',
    )
    second_streamed = _streaming_body(second_response)
    assert second_streamed == f'data: {MERGED_IN_PREVIOUS_RESPONSE_TOKEN}\n\n'

    third_response = client.post(
        '/api/chat',
        data={'message': 'fever', 'session_id': session_id},
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {access}',
    )
    third_streamed = _streaming_body(third_response)
    assert third_streamed == 'data: fragment-merged-response\n\n'

    assert FakeAgent.seen_prompts == ['i have fever']
