from ninja import Router

router = Router()

# Import endpoint modules to register their routes on the shared router.
# Each module uses `from chatbot.features.chat.api import router` and decorates
# its views with @router.get / @router.post / etc.
from . import history
from . import post_chat
from . import sessions
from . import get_structured_interaction
from . import save_structured_interaction
from .post_chat import (  # noqa: E402
    CHAT_DEBOUNCE_WINDOW_SECONDS,
    MERGED_IN_PREVIOUS_RESPONSE_TOKEN,
    OpenRouterAgent,
)
from .utils import _serialize_chat_session  # noqa: E402

router.add_router('', history.router)
router.add_router('', post_chat.router)
router.add_router('', sessions.router)
router.add_router('', get_structured_interaction.router)
router.add_router('', save_structured_interaction.router)

__all__ = [
    'CHAT_DEBOUNCE_WINDOW_SECONDS',
    'MERGED_IN_PREVIOUS_RESPONSE_TOKEN',
    'OpenRouterAgent',
    '_serialize_chat_session',
    'router',
]
