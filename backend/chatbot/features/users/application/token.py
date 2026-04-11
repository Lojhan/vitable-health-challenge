from __future__ import annotations

from typing import Any, Protocol


class TokenUnitOfWork(Protocol):
    """Application-layer contract for user lookup during token operations."""

    def get_user_by_id(self, user_id: int) -> Any: ...
