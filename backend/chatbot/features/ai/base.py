from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel


class UserProfileSchema(BaseModel):
    first_name: str
    insurance_tier: Literal['Bronze', 'Silver', 'Gold']


class CalculateVisitCostInputSchema(BaseModel):
    insurance_tier: Literal['Bronze', 'Silver', 'Gold']
    visit_type: str


class CheckAvailabilityInputSchema(BaseModel):
    date_range_str: str
    provider_id: int | None = None


class ResolveDatetimeReferenceInputSchema(BaseModel):
    datetime_reference: str


class BookAppointmentInputSchema(BaseModel):
    appointment_id: int | None = None
    time_slot: str
    rrule_str: str | None = None
    symptoms_summary: str
    appointment_reason: str
    provider_id: int | None = None


class ListMyAppointmentsInputSchema(BaseModel):
    pass


class ListProvidersInputSchema(BaseModel):
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


class BaseAgentInterface(ABC):
    @classmethod
    def get_tools(cls) -> list[dict]:
        return [
            {
                'type': 'function',
                'function': {
                    'name': 'calculate_visit_cost',
                    'description': (
                        'Calculate a visit cost based on insurance tier and visit type.'
                    ),
                    'parameters': CalculateVisitCostInputSchema.model_json_schema(),
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'resolve_datetime_reference',
                    'description': (
                        'Resolve relative datetime expressions (for example: '
                        'tomorrow, next monday at 9am) into an absolute UTC ISO '
                        'datetime string based on current server datetime.'
                    ),
                    'parameters': ResolveDatetimeReferenceInputSchema.model_json_schema(),
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'check_availability',
                    'description': (
                        'Check available appointment slots for a date range '
                        'while honoring RRULE conflicts.'
                    ),
                    'parameters': CheckAvailabilityInputSchema.model_json_schema(),
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'book_appointment',
                    'description': (
                        'Book an appointment for the authenticated user and '
                        'optionally store RRULE. Requires symptoms summary and '
                        'appointment reason.'
                    ),
                    'parameters': BookAppointmentInputSchema.model_json_schema(),
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'list_my_appointments',
                    'description': 'List appointments for the authenticated user.',
                    'parameters': ListMyAppointmentsInputSchema.model_json_schema(),
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'cancel_my_appointment',
                    'description': 'Cancel an appointment for the authenticated user.',
                    'parameters': CancelMyAppointmentInputSchema.model_json_schema(),
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'update_my_appointment',
                    'description': (
                        'Update time slot, RRULE, or provider for an authenticated user '
                        'appointment.'
                    ),
                    'parameters': UpdateMyAppointmentInputSchema.model_json_schema(),
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'list_providers',
                    'description': (
                        'List all available healthcare providers with their name, '
                        'specialty, and provider_id. Call this before scheduling to '
                        'let the user choose a provider.'
                    ),
                    'parameters': ListProvidersInputSchema.model_json_schema(),
                },
            },
        ]

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        """Generate an AI response for the provided prompt."""
