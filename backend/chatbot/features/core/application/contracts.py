from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Any


class BaseUseCase(ABC):
    """Marker base class for application-layer use case implementations."""


class BaseUnitOfWork(ABC):
    """Common unit-of-work contract enforced for infrastructure implementations."""

    @abstractmethod
    def __enter__(self) -> Any:
        raise NotImplementedError

    @abstractmethod
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        raise NotImplementedError
