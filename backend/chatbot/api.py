from ninja import NinjaAPI

from chatbot.features.chat.api import (
	CHAT_DEBOUNCE_WINDOW_SECONDS,
	MERGED_IN_PREVIOUS_RESPONSE_TOKEN,
	OpenRouterAgent,
	_serialize_chat_session,
)
from chatbot.features.chat.api import router as chat_router
from chatbot.features.users.api.auth import router as auth_router

api = NinjaAPI()
api.add_router('/auth', auth_router, tags=['Authentication'], auth=None)
api.add_router('', chat_router)

__all__ = [
	'CHAT_DEBOUNCE_WINDOW_SECONDS',
	'MERGED_IN_PREVIOUS_RESPONSE_TOKEN',
	'OpenRouterAgent',
	'_serialize_chat_session',
	'api',
]
