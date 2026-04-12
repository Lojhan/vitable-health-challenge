from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Protocol


class ChatUnitOfWork(Protocol):
    """Application-layer contract for chat persistence operations."""

    def get_or_create_session(self, *, user: Any, session_id: int | None) -> Any: ...

    def create_user_messages(
        self,
        *,
        session: Any,
        contents: list[str],
        request_id: str | None = None,
    ) -> list[Any]: ...

    def user_message_exists_with_request_id(
        self,
        *,
        session: Any,
        request_id: str,
    ) -> bool: ...

    def session_critical_section(
        self,
        *,
        session_id: int,
    ) -> AbstractContextManager[Any]: ...

    def get_ordered_messages(self, *, session: Any) -> list[Any]: ...

    def create_assistant_message(
        self,
        *,
        session: Any,
        content: str,
        message_kind: str,
    ) -> None: ...

    def delete_session(self, *, user_id: int, session_id: int) -> bool: ...

    def list_user_session_summaries_page(
        self,
        *,
        user_id: int,
        cursor: str | None,
        page_size: int,
    ) -> tuple[list[Any], str | None, bool]: ...

    def get_user_session_prefetched(self, *, user_id: int, session_id: int) -> Any | None: ...

    def get_history_sync_payload(self, *, user_id: int) -> dict[str, object]: ...

    def get_structured_interaction_selection(
        self,
        *,
        user_id: int,
        interaction_id: str,
    ) -> dict[str, Any] | None: ...

    def save_structured_interaction_selection(
        self,
        *,
        user_id: int,
        interaction_id: str,
        kind: str,
        selection: dict[str, Any],
    ) -> dict[str, Any]: ...
