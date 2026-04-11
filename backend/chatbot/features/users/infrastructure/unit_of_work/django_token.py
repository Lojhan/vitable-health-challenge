from __future__ import annotations

from types import TracebackType
from typing import Any

from django.contrib.auth import get_user_model

from chatbot.features.core.application.contracts import BaseUnitOfWork


class DjangoTokenUnitOfWork(BaseUnitOfWork):
    """Infrastructure implementation for user lookup during token operations."""

    def __enter__(self) -> DjangoTokenUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        pass

    def get_user_by_id(self, user_id: int) -> Any:
        user_model = get_user_model()
        return user_model.objects.get(id=user_id)
