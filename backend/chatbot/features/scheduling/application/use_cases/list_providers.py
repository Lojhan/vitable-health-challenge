from collections.abc import Callable

from chatbot.features.core.application.contracts import BaseUseCase
from chatbot.features.scheduling.application.common import ProviderSchema
from chatbot.features.scheduling.application.unit_of_work import SchedulingUnitOfWork


class ListProvidersUseCase(BaseUseCase):
    def __init__(
        self,
        *,
        uow_factory: Callable[[], SchedulingUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(self) -> list[ProviderSchema]:
        with self._uow_factory() as uow:
            return [
                {
                    'provider_id': int(provider.pk),
                    'name': provider.name,
                    'specialty': provider.specialty,
                }
                for provider in uow.list_providers()
            ]
