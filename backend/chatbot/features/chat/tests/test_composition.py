import json

import pytest
from django.contrib.auth import get_user_model

from chatbot.features.chat.composition import build_save_assistant_response_fn
from chatbot.features.chat.models import ChatMessage, ChatSession
from chatbot.features.chat.stream_protocol import encode_tool_result


@pytest.mark.django_db(transaction=True)
def test_save_assistant_response_persists_only_final_structured_tool_results():
	user_model = get_user_model()
	user = user_model.objects.create_user(
		username='chat-composition-user',
		password='safe-password-123',
	)
	session = ChatSession.objects.create(user=user)

	save_response = build_save_assistant_response_fn(session=session)
	save_response([
		encode_tool_result(
			tool_name='show_providers_for_selection',
			tool_call_id='tool-1',
			ui_kind='providers',
			result={
				'type': 'providers',
				'interaction_id': 'tool-1',
				'ui_state': 'skeleton',
				'providers': [],
			},
		),
		encode_tool_result(
			tool_name='show_providers_for_selection',
			tool_call_id='tool-1',
			ui_kind='providers',
			result={
				'type': 'providers',
				'interaction_id': 'tool-1',
				'ui_state': 'partial',
				'providers': [],
			},
		),
		encode_tool_result(
			tool_name='show_providers_for_selection',
			tool_call_id='tool-1',
			ui_kind='providers',
			result={
				'type': 'providers',
				'interaction_id': 'tool-1',
				'ui_state': 'final',
				'providers': [
					{'provider_id': 1, 'name': 'Dr. Lee', 'specialty': 'General Practice'},
				],
			},
		),
	])

	messages = list(ChatMessage.objects.filter(session=session, role=ChatMessage.ROLE_ASSISTANT))
	assert len(messages) == 1
	assert messages[0].message_kind == ChatMessage.MessageKind.PROVIDERS
	assert json.loads(messages[0].content)['ui_state'] == 'final'