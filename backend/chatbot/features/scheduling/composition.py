from chatbot.features.scheduling.infrastructure.unit_of_work.django_scheduling import (
    DjangoSchedulingUnitOfWork,
)


def build_scheduling_uow_factory() -> type[DjangoSchedulingUnitOfWork]:
    return DjangoSchedulingUnitOfWork
