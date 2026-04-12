from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict, cast

from dateutil.parser import parse as parse_datetime
from django.db.models import DateTimeField
from django.utils import timezone

from chatbot.features.scheduling.models import Appointment


class ProviderSchema(TypedDict):
    provider_id: int
    name: str
    specialty: str


class SerializedAppointment(TypedDict):
    appointment_id: int
    title: str
    time_slot: str
    time_slot_human_utc: str
    rrule: str
    symptoms_summary: str
    appointment_reason: str
    provider_id: int | None
    provider_name: str | None


class FutureAppointmentsPayload(TypedDict):
    current_datetime_utc: str
    count: int
    appointments: list[SerializedAppointment]
    formatted_lines: list[str]
    summary: str


class AvailabilityProviderPayload(TypedDict):
    provider_id: int
    name: str
    specialty: str


class AvailabilityPayload(TypedDict, total=False):
    type: str
    timezone: str
    appointment_duration_minutes: int
    appointment_duration_note: str
    requested_window_start_utc: str
    requested_window_end_utc: str
    availability_source: str
    provider: AvailabilityProviderPayload | None
    availability_dtstart_utc: str | None
    availability_rrule: str | None
    blocked_slots_utc: list[str]
    available_slots_utc: list[str]


class CancelAppointmentResult(TypedDict):
    appointment_id: int
    cancelled: bool


class UpdateAppointmentMissingResult(TypedDict):
    appointment_id: int
    updated: bool
    reason: str


class UpdateAppointmentSuccessResult(TypedDict):
    appointment_id: int
    updated: bool
    appointment: SerializedAppointment


UpdateAppointmentResult = UpdateAppointmentMissingResult | UpdateAppointmentSuccessResult


def appointment_id(appointment: Appointment) -> int:
    return cast(int, cast(Any, appointment).id)


def appointment_time_slot_field() -> DateTimeField:
    return cast(DateTimeField, Appointment._meta.get_field('time_slot'))


def coerce_appointment_id(raw_value: object) -> int | None:
    if isinstance(raw_value, int):
        return raw_value

    if isinstance(raw_value, str):
        match = re.search(r'\d+', raw_value)
        if match is not None:
            return int(match.group(0))

    return None


def normalize_datetime(value: datetime) -> datetime:
    if timezone.is_naive(value):
        return timezone.make_aware(value, UTC)

    return value.astimezone(UTC)


def display_datetime(value: datetime) -> str:
    return timezone.make_naive(value, UTC).replace(microsecond=0).isoformat()


def display_human_datetime_utc(value: datetime) -> str:
    normalized = normalize_datetime(value)
    return normalized.strftime('%A, %B %d, %Y at %I:%M %p UTC')


def has_explicit_time(raw_value: str) -> bool:
    normalized = raw_value.lower()
    return bool(
        re.search(r'\b\d{1,2}:\d{2}\b', normalized)
        or re.search(r'\b\d{1,2}\s*(am|pm)\b', normalized)
        or re.search(r'\bt\d{2}:\d{2}', normalized)
        or 'utc' in normalized
    )


def resolve_datetime_reference_value(datetime_reference: str) -> dict[str, object]:
    now = timezone.now().astimezone(UTC)
    normalized_reference = datetime_reference.strip().lower()

    if not normalized_reference:
        return {
            'resolved': False,
            'reference': datetime_reference,
            'reason': 'empty_reference',
        }

    base_date = now.date()

    weekday_match = re.search(
        r'\b(?:next\s+|this\s+|on\s+)?(monday|mon|tuesday|tue|wednesday|wed|thursday|thu|friday|fri|saturday|sat|sunday|sun)\b',
        normalized_reference,
    )

    if 'tomorrow' in normalized_reference:
        base_date = (now + timedelta(days=1)).date()
    elif 'today' in normalized_reference:
        base_date = now.date()
    elif weekday_match:
        prefix = (weekday_match.group(0) or '').split()[0] if ' ' in weekday_match.group(0) else ''
        day_str = weekday_match.groups()[-1]

        weekdays = {
            'monday': 0,
            'mon': 0,
            'tuesday': 1,
            'tue': 1,
            'wednesday': 2,
            'wed': 2,
            'thursday': 3,
            'thu': 3,
            'friday': 4,
            'fri': 4,
            'saturday': 5,
            'sat': 5,
            'sunday': 6,
            'sun': 6,
        }
        requested_weekday = weekdays[day_str]
        days_ahead = (requested_weekday - now.weekday()) % 7

        if days_ahead == 0 and prefix == 'next':
            days_ahead = 7

        base_date = (now + timedelta(days=days_ahead)).date()

    reference_without_relative_tokens = re.sub(
        r'\b(?:tomorrow|today|(?:next\s+|this\s+|on\s+)?(?:monday|mon|tuesday|tue|wednesday|wed|thursday|thu|friday|fri|saturday|sat|sunday|sun))\b',
        '',
        normalized_reference,
    ).strip()

    default_datetime = now.replace(
        year=base_date.year,
        month=base_date.month,
        day=base_date.day,
        hour=9,
        minute=0,
        second=0,
        microsecond=0,
    )

    if not reference_without_relative_tokens:
        resolved = default_datetime
    else:
        try:
            resolved = parse_datetime(
                reference_without_relative_tokens,
                default=default_datetime,
                fuzzy=True,
            )
        except (TypeError, ValueError):
            return {
                'resolved': False,
                'reference': datetime_reference,
                'reason': 'unable_to_parse',
            }

    resolved = normalize_datetime(resolved)
    return {
        'resolved': True,
        'reference': datetime_reference,
        'iso_datetime_utc': display_datetime(resolved),
        'resolved_from_now_utc': display_datetime(now),
    }


def parse_datetime_input(raw_value: str) -> datetime:
    time_slot_field = appointment_time_slot_field()
    try:
        parsed = time_slot_field.to_python(raw_value)
        return normalize_datetime(parsed)
    except Exception as error:
        resolved = resolve_datetime_reference_value(raw_value)
        if not resolved.get('resolved'):
            raise ValueError(f'Unable to parse datetime value: {raw_value}') from error
        iso_datetime_utc = resolved.get('iso_datetime_utc')
        if not iso_datetime_utc:
            raise ValueError(f'Unable to resolve datetime value: {raw_value}') from error
        parsed = time_slot_field.to_python(iso_datetime_utc)
        return normalize_datetime(parsed)


def _normalize_range_separator(date_range_str: str) -> str:
    normalized = date_range_str.strip()
    if '/' in normalized:
        return normalized

    separator_match = re.search(
        r'(?P<left>.+?)\s+(?:to|through|until)\s+(?P<right>.+)',
        normalized,
        flags=re.IGNORECASE,
    )
    if not separator_match:
        return normalized

    left = separator_match.group('left').strip()
    right = separator_match.group('right').strip()
    if not left or not right:
        return normalized

    return f'{left}/{right}'


def _resolve_named_date_window(date_range_str: str) -> tuple[datetime, datetime] | None:
    normalized = date_range_str.strip().lower()
    now = timezone.now().astimezone(UTC)

    if normalized in {'this month', 'current month'}:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end

    if normalized == 'next month':
        if now.month == 12:
            start = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            start = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end

    if normalized in {'this week', 'current week'}:
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
        return start, end

    if normalized == 'next week':
        start = (now - timedelta(days=now.weekday()) + timedelta(days=7)).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        end = start + timedelta(days=7)
        return start, end

    month_match = re.fullmatch(
        r'(?:rest of|end of)\s+(january|february|march|april|may|june|july|august|september|october|november|december)',
        normalized,
    )
    if month_match:
        month_names = {
            'january': 1,
            'february': 2,
            'march': 3,
            'april': 4,
            'may': 5,
            'june': 6,
            'july': 7,
            'august': 8,
            'september': 9,
            'october': 10,
            'november': 11,
            'december': 12,
        }
        target_month = month_names[month_match.group(1)]
        target_year = now.year + (1 if target_month < now.month else 0)
        start = now.replace(year=target_year, month=target_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        if normalized.startswith('rest of') and target_month == now.month and target_year == now.year:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if target_month == 12:
            end = start.replace(year=target_year + 1, month=1, day=1)
        else:
            end = start.replace(month=target_month + 1, day=1)
        return start, end

    return None


def resolve_date_range_input(date_range_str: str) -> tuple[datetime, datetime]:
    named_window = _resolve_named_date_window(date_range_str)
    if named_window is not None:
        return named_window

    normalized_range = _normalize_range_separator(date_range_str)

    if '/' in normalized_range:
        start_str, end_str = normalized_range.split('/', maxsplit=1)
        start = parse_datetime_input(start_str)
        end = parse_datetime_input(end_str)
        if end <= start:
            end = start + timedelta(hours=1)
        return start, end

    anchor = parse_datetime_input(normalized_range)

    if has_explicit_time(normalized_range):
        start = anchor
        end = start + timedelta(hours=8)
        return start, end

    start = anchor.replace(hour=9, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=8)
    return start, end


def serialize_appointment(appointment: Appointment) -> SerializedAppointment:
    provider_id: int | None = cast(int, appointment.provider_id) if appointment.provider_id is not None else None
    provider_name: str | None = appointment.provider.name if appointment.provider_id is not None else None
    return {
        'appointment_id': appointment_id(appointment),
        'title': appointment.title,
        'time_slot': display_datetime(appointment.time_slot),
        'time_slot_human_utc': display_human_datetime_utc(appointment.time_slot),
        'rrule': appointment.rrule,
        'symptoms_summary': appointment.symptoms_summary,
        'appointment_reason': appointment.appointment_reason,
        'provider_id': provider_id,
        'provider_name': provider_name,
    }


def format_future_appointments_payload(
    appointments: list[Appointment],
) -> FutureAppointmentsPayload:
    serialized = [serialize_appointment(appointment) for appointment in appointments]

    if not serialized:
        return {
            'current_datetime_utc': display_datetime(timezone.now()),
            'count': 0,
            'appointments': [],
            'formatted_lines': [],
            'summary': 'You have no upcoming appointments.',
        }

    formatted_lines: list[str] = []
    for item in serialized:
        formatted_lines.append(
            f"- Appointment #{item['appointment_id']}: "
            f"{item['time_slot_human_utc']}"
            f" | Reason: {item['appointment_reason'] or 'Not provided'}"
            f" | Symptoms: {item['symptoms_summary'] or 'Not provided'}"
        )

    return {
        'current_datetime_utc': display_datetime(timezone.now()),
        'count': len(serialized),
        'appointments': serialized,
        'formatted_lines': formatted_lines,
        'summary': f"You have {len(serialized)} upcoming appointment(s).",
    }
