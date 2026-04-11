from chatbot.features.chat.message_burst import (
    build_prompt_from_pending_user_messages,
    is_incomplete_fragment,
    should_defer_response,
    split_incoming_message_payload,
)


class FakeMessage:
    def __init__(self, content: str):
        self.content = content


def test_split_incoming_message_payload_splits_separator_and_trims():
    payload = split_incoming_message_payload(
        'i<USER_MESSAGE_BURST_SEPARATOR> have <USER_MESSAGE_BURST_SEPARATOR> fever'
    )

    assert payload == ['i', 'have', 'fever']


def test_build_prompt_from_pending_user_messages_merges_fragments():
    prompt = build_prompt_from_pending_user_messages(
        [FakeMessage('i'), FakeMessage('have'), FakeMessage('fever')]
    )

    assert prompt == 'i have fever'


def test_is_incomplete_fragment_detects_connective_only_message():
    assert is_incomplete_fragment('and') is True
    assert is_incomplete_fragment('I have fever.') is False


def test_should_defer_response_requires_all_pending_messages_to_be_incomplete():
    assert should_defer_response([FakeMessage('i'), FakeMessage('have')]) is True
    assert should_defer_response([FakeMessage('i'), FakeMessage('fever')]) is False
