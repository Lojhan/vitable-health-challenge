from datetime import UTC
from typing import Any, cast

from pydantic import BaseModel, ValidationInfo, field_validator

from chatbot.features.ai.tooling import ToolContract
from chatbot.features.core.domain.validation import require_non_blank_text
from chatbot.features.scheduling.application.common import (
    AvailabilityPayload,
    CancelAppointmentResult,
    FutureAppointmentsPayload,
    ProviderSchema,
    UpdateAppointmentResult,
)
from chatbot.features.scheduling.application.use_cases.book_appointment import (
    BookAppointmentUseCase,
)
from chatbot.features.scheduling.application.use_cases.cancel_user_appointment import (
    CancelUserAppointmentUseCase,
)
from chatbot.features.scheduling.application.use_cases.describe_availability import (
    DescribeAvailabilityUseCase,
)
from chatbot.features.scheduling.application.use_cases.list_providers import (
    ListProvidersUseCase,
)
from chatbot.features.scheduling.application.use_cases.list_user_appointments import (
    ListUserAppointmentsUseCase,
)
from chatbot.features.scheduling.application.use_cases.resolve_datetime_reference import (
    ResolveDatetimeReferenceUseCase,
)
from chatbot.features.scheduling.application.use_cases.update_user_appointment import (
    UpdateUserAppointmentUseCase,
)
from chatbot.features.scheduling.infrastructure.unit_of_work.django_scheduling import (
    DjangoSchedulingUnitOfWork,
)


def _strip_and_require_text(value: str, field_name: str) -> str:
    return require_non_blank_text(value, field=field_name)


class CheckAvailabilityInputSchema(BaseModel):
    date_range_str: str
    provider_id: int | None = None

    @field_validator('date_range_str')
    @classmethod
    def validate_date_range_str(
        cls: type['CheckAvailabilityInputSchema'],
        value: str,
    ) -> str:
        return _strip_and_require_text(value, 'date_range_str')


class ResolveDatetimeReferenceInputSchema(BaseModel):
    datetime_reference: str

    @field_validator('datetime_reference')
    @classmethod
    def validate_datetime_reference(
        cls: type['ResolveDatetimeReferenceInputSchema'],
        value: str,
    ) -> str:
        return _strip_and_require_text(value, 'datetime_reference')


class BookAppointmentInputSchema(BaseModel):
    appointment_id: int | None = None
    time_slot: str
    rrule_str: str | None = None
    symptoms_summary: str
    appointment_reason: str
    provider_id: int | None = None

    @field_validator('time_slot', 'symptoms_summary', 'appointment_reason')
    @classmethod
    def validate_required_text(
        cls: type['BookAppointmentInputSchema'],
        value: str,
        info: ValidationInfo,
    ) -> str:
        return _strip_and_require_text(value, info.field_name)


class ListMyAppointmentsInputSchema(BaseModel):
    pass


class ListProvidersInputSchema(BaseModel):
    pass


class ShowProvidersForSelectionInputSchema(BaseModel):
    pass


class CancelMyAppointmentInputSchema(BaseModel):
    appointment_id: int


class UpdateMyAppointmentInputSchema(BaseModel):
    appointment_id: int
    time_slot: str | None = None
    rrule_str: str | None = None
    symptoms_summary: str | None = None
    appointment_reason: str | None = None
    provider_id: int | None = None

    @field_validator('time_slot', 'rrule_str', 'symptoms_summary', 'appointment_reason')
    @classmethod
    def validate_optional_text(
        cls: type['UpdateMyAppointmentInputSchema'],
        value: str | None,
        info: ValidationInfo,
    ) -> str | None:
        if value is None:
            return None
        return _strip_and_require_text(value, info.field_name)


def resolve_datetime_reference(datetime_reference: str) -> dict[str, object]:
    return ResolveDatetimeReferenceUseCase().execute(
        datetime_reference=datetime_reference,
    )


def list_providers() -> list[ProviderSchema]:
    return ListProvidersUseCase(uow_factory=DjangoSchedulingUnitOfWork).execute()


def describe_availability(
    date_range_str: str,
    provider_id: int | None = None,
) -> AvailabilityPayload:
    return DescribeAvailabilityUseCase(uow_factory=DjangoSchedulingUnitOfWork).execute(
        date_range_str=date_range_str,
        provider_id=provider_id,
    )


def list_user_appointments(user_id: int) -> FutureAppointmentsPayload:
    return ListUserAppointmentsUseCase(uow_factory=DjangoSchedulingUnitOfWork).execute(
        user_id=user_id,
    )


def book_appointment(
    user_id: int,
    time_slot: str,
    rrule_str: str | None = None,
    symptoms_summary: str = '',
    appointment_reason: str = '',
    appointment_id: int | str | None = None,
    provider_id: int | None = None,
) -> object:
    return BookAppointmentUseCase(uow_factory=DjangoSchedulingUnitOfWork).execute(
        user_id=user_id,
        time_slot=time_slot,
        rrule_str=rrule_str,
        symptoms_summary=symptoms_summary,
        appointment_reason=appointment_reason,
        appointment_id=appointment_id,
        provider_id=provider_id,
    )


def cancel_user_appointment(
    user_id: int,
    appointment_id: int | str,
) -> CancelAppointmentResult:
    return CancelUserAppointmentUseCase(uow_factory=DjangoSchedulingUnitOfWork).execute(
        user_id=user_id,
        appointment_id=appointment_id,
    )


def update_user_appointment(
    user_id: int,
    appointment_id: int | str,
    time_slot: str | None = None,
    rrule_str: str | None = None,
    symptoms_summary: str | None = None,
    appointment_reason: str | None = None,
    provider_id: int | None = None,
) -> UpdateAppointmentResult:
    return UpdateUserAppointmentUseCase(uow_factory=DjangoSchedulingUnitOfWork).execute(
        user_id=user_id,
        appointment_id=appointment_id,
        time_slot=time_slot,
        rrule_str=rrule_str,
        symptoms_summary=symptoms_summary,
        appointment_reason=appointment_reason,
        provider_id=provider_id,
    )


def _execute_resolve_datetime_reference(
    arguments: dict[str, Any],
    _user_id: int | None,
) -> object:
    return resolve_datetime_reference(datetime_reference=arguments['datetime_reference'])


def _execute_check_availability(
    arguments: dict[str, Any],
    _user_id: int | None,
) -> object:
    return describe_availability(
        date_range_str=arguments['date_range_str'],
        provider_id=arguments.get('provider_id'),
    )


def _execute_list_providers(arguments: dict[str, Any], _user_id: int | None) -> object:
    _ = arguments
    return list_providers()


def _execute_show_providers_for_selection(
    arguments: dict[str, Any],
    _user_id: int | None,
) -> object:
    _ = arguments
    return list_providers()


def _require_authenticated_user_id(user_id: int | None) -> int:
    if user_id is None:
        raise ValueError('Authenticated user_id is required for appointment tools')
    return user_id


def _execute_book_appointment(arguments: dict[str, Any], user_id: int | None) -> object:
    authenticated_user_id = _require_authenticated_user_id(user_id)
    appointment = book_appointment(
        user_id=authenticated_user_id,
        appointment_id=arguments.get('appointment_id'),
        time_slot=arguments['time_slot'],
        rrule_str=arguments.get('rrule_str'),
        symptoms_summary=arguments['symptoms_summary'],
        appointment_reason=arguments['appointment_reason'],
        provider_id=arguments.get('provider_id'),
    )
    appointment_obj = cast(Any, appointment)
    appointment_provider_id = appointment_obj.provider_id
    return {
        'appointment_id': int(appointment_obj.pk),
        'provider_id': int(appointment_provider_id)
        if appointment_provider_id is not None
        else None,
        'time_slot_utc': appointment_obj.time_slot.astimezone(UTC).replace(
            microsecond=0
        ).isoformat(),
        'time_slot_human_utc': appointment_obj.time_slot.astimezone(UTC).strftime(
            '%A, %B %d, %Y at %I:%M %p UTC'
        ),
    }


def _execute_list_my_appointments(arguments: dict[str, Any], user_id: int | None) -> object:
    _ = arguments
    authenticated_user_id = _require_authenticated_user_id(user_id)
    return list_user_appointments(user_id=authenticated_user_id)


def _execute_cancel_my_appointment(arguments: dict[str, Any], user_id: int | None) -> object:
    authenticated_user_id = _require_authenticated_user_id(user_id)
    return cancel_user_appointment(
        user_id=authenticated_user_id,
        appointment_id=arguments['appointment_id'],
    )


def _execute_update_my_appointment(arguments: dict[str, Any], user_id: int | None) -> object:
    authenticated_user_id = _require_authenticated_user_id(user_id)
    return update_user_appointment(
        user_id=authenticated_user_id,
        appointment_id=arguments['appointment_id'],
        time_slot=arguments.get('time_slot'),
        rrule_str=arguments.get('rrule_str'),
        symptoms_summary=arguments.get('symptoms_summary'),
        appointment_reason=arguments.get('appointment_reason'),
        provider_id=arguments.get('provider_id'),
    )


SCHEDULING_TOOL_CONTRACTS = [
    ToolContract(
        name='resolve_datetime_reference',
        description=(
            'Resolve relative datetime expressions (for example: tomorrow, '
            'next monday at 9am) into an absolute UTC ISO datetime string '
            'based on current server datetime.'
        ),
        input_schema=ResolveDatetimeReferenceInputSchema,
        executor=_execute_resolve_datetime_reference,
    ),
    ToolContract(
        name='check_availability',
        description='Check available appointment slots for a date range while honoring RRULE conflicts.',
        input_schema=CheckAvailabilityInputSchema,
        executor=_execute_check_availability,
    ),
    ToolContract(
        name='book_appointment',
        description=(
            'Book an appointment for the authenticated user and optionally '
            'store RRULE. Requires symptoms summary and appointment reason.'
        ),
        input_schema=BookAppointmentInputSchema,
        executor=_execute_book_appointment,
    ),
    ToolContract(
        name='list_my_appointments',
        description='List appointments for the authenticated user.',
        input_schema=ListMyAppointmentsInputSchema,
        executor=_execute_list_my_appointments,
    ),
    ToolContract(
        name='cancel_my_appointment',
        description='Cancel an appointment for the authenticated user.',
        input_schema=CancelMyAppointmentInputSchema,
        executor=_execute_cancel_my_appointment,
    ),
    ToolContract(
        name='update_my_appointment',
        description='Update time slot, RRULE, or provider for an authenticated user appointment.',
        input_schema=UpdateMyAppointmentInputSchema,
        executor=_execute_update_my_appointment,
    ),
    ToolContract(
        name='list_providers',
        description=(
            'Resolve available healthcare providers into provider_id values for '
            'internal scheduling workflow steps, including matching a provider name '
            'mentioned by the user. This tool is backend-only and should not be used '
            'when you want to show a provider list to the user.'
        ),
        input_schema=ListProvidersInputSchema,
        executor=_execute_list_providers,
    ),
    ToolContract(
        name='show_providers_for_selection',
        description=(
            'Show the user a list of available healthcare providers with name, '
            'specialty, and provider_id when they explicitly ask to browse or choose '
            'from provider options.'
        ),
        input_schema=ShowProvidersForSelectionInputSchema,
        executor=_execute_show_providers_for_selection,
    ),
]
