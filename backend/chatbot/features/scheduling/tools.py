import re
from datetime import timedelta
from datetime import timezone as dt_timezone
from typing import Any, TypedDict, cast

from dateutil.parser import parse as parse_datetime
from dateutil.rrule import rrulestr
from django.contrib.auth import get_user_model
from django.db.models import DateTimeField
from django.utils import timezone

from chatbot.features.scheduling.models import Appointment


class SerializedAppointment(TypedDict):
    appointment_id: int
    title: str
    time_slot: str
    time_slot_human_utc: str
    rrule: str
    symptoms_summary: str
    appointment_reason: str


class FutureAppointmentsPayload(TypedDict):
    current_datetime_utc: str
    count: int
    appointments: list[SerializedAppointment]
    formatted_lines: list[str]
    summary: str


class ResolveDatetimeReferenceResult(TypedDict, total=False):
    resolved: bool
    reference: str
    reason: str
    iso_datetime_utc: str
    resolved_from_now_utc: str


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


def _appointment_id(appointment: Appointment) -> int:
    return cast(int, cast(Any, appointment).id)


def _appointment_time_slot_field() -> DateTimeField:
    return cast(DateTimeField, Appointment._meta.get_field('time_slot'))


def _normalize_datetime(value):
    if timezone.is_naive(value):
        return timezone.make_aware(value, dt_timezone.utc)

    return value.astimezone(dt_timezone.utc)


def _display_datetime(value):
    return timezone.make_naive(value, dt_timezone.utc).replace(microsecond=0).isoformat()


def _display_human_datetime_utc(value) -> str:
    normalized = _normalize_datetime(value)
    return normalized.strftime('%A, %B %d, %Y at %I:%M %p UTC')


def _parse_datetime_input(raw_value: str):
    time_slot_field = _appointment_time_slot_field()
    try:
        parsed = time_slot_field.to_python(raw_value)
        return _normalize_datetime(parsed)
    except Exception:
        resolved = resolve_datetime_reference(raw_value)
        if not resolved.get('resolved'):
            raise ValueError(f'Unable to parse datetime value: {raw_value}')
        iso_datetime_utc = resolved.get('iso_datetime_utc')
        if not iso_datetime_utc:
            raise ValueError(f'Unable to resolve datetime value: {raw_value}')
        parsed = time_slot_field.to_python(iso_datetime_utc)
        return _normalize_datetime(parsed)


def _has_explicit_time(raw_value: str) -> bool:
    normalized = raw_value.lower()
    return bool(
        re.search(r'\b\d{1,2}:\d{2}\b', normalized)
        or re.search(r'\b\d{1,2}\s*(am|pm)\b', normalized)
        or re.search(r'\bt\d{2}:\d{2}', normalized)
        or 'utc' in normalized
    )


def _resolve_date_range_input(date_range_str: str) -> tuple:
    normalized_range = date_range_str.strip()

    if '/' in normalized_range:
        start_str, end_str = normalized_range.split('/', maxsplit=1)
        start = _parse_datetime_input(start_str)
        end = _parse_datetime_input(end_str)
        if end <= start:
            end = start + timedelta(hours=1)
        return start, end

    anchor = _parse_datetime_input(normalized_range)

    if _has_explicit_time(normalized_range):
        start = anchor
        end = start + timedelta(hours=8)
        return start, end

    start = anchor.replace(hour=9, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=8)
    return start, end


def _serialize_appointment(appointment: Appointment) -> SerializedAppointment:
    return {
        'appointment_id': _appointment_id(appointment),
        'title': appointment.title,
        'time_slot': _display_datetime(appointment.time_slot),
        'time_slot_human_utc': _display_human_datetime_utc(appointment.time_slot),
        'rrule': appointment.rrule,
        'symptoms_summary': appointment.symptoms_summary,
        'appointment_reason': appointment.appointment_reason,
    }


def _format_future_appointments_payload(
    appointments: list[Appointment],
) -> FutureAppointmentsPayload:
    serialized = [_serialize_appointment(appointment) for appointment in appointments]

    if not serialized:
        return {
            'current_datetime_utc': _display_datetime(timezone.now()),
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
        'current_datetime_utc': _display_datetime(timezone.now()),
        'count': len(serialized),
        'appointments': serialized,
        'formatted_lines': formatted_lines,
        'summary': f"You have {len(serialized)} upcoming appointment(s).",
    }


def resolve_datetime_reference(datetime_reference: str) -> ResolveDatetimeReferenceResult:
    now = timezone.now().astimezone(dt_timezone.utc)
    normalized_reference = datetime_reference.strip().lower()

    if not normalized_reference:
        return {
            'resolved': False,
            'reference': datetime_reference,
            'reason': 'empty_reference',
        }

    base_date = now.date()
    next_weekday_match = re.search(
        r'next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
        normalized_reference,
    )

    if 'tomorrow' in normalized_reference:
        base_date = (now + timedelta(days=1)).date()
    elif 'today' in normalized_reference:
        base_date = now.date()
    elif next_weekday_match:
        weekdays = {
            'monday': 0,
            'tuesday': 1,
            'wednesday': 2,
            'thursday': 3,
            'friday': 4,
            'saturday': 5,
            'sunday': 6,
        }
        requested_weekday = weekdays[next_weekday_match.group(1)]
        days_ahead = (requested_weekday - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        base_date = (now + timedelta(days=days_ahead)).date()

    reference_without_relative_tokens = re.sub(
        r'\b(tomorrow|today|next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b',
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

    try:
        resolved = parse_datetime(
            reference_without_relative_tokens or normalized_reference,
            default=default_datetime,
            fuzzy=True,
        )
    except (TypeError, ValueError):
        return {
            'resolved': False,
            'reference': datetime_reference,
            'reason': 'unable_to_parse',
        }

    resolved = _normalize_datetime(resolved)
    return {
        'resolved': True,
        'reference': datetime_reference,
        'iso_datetime_utc': _display_datetime(resolved),
        'resolved_from_now_utc': _display_datetime(now),
    }


def check_availability(date_range_str: str) -> list[str]:
    start, end = _resolve_date_range_input(date_range_str)

    occupied = set()
    for appointment in Appointment.objects.all():
        rule = rrulestr(appointment.rrule, dtstart=appointment.time_slot)
        for occurrence in rule.between(start, end, inc=True):
            normalized_occurrence = _normalize_datetime(occurrence)
            occupied.add(_display_datetime(normalized_occurrence))

    available_slots = []
    current = start
    while current < end:
        candidate = _display_datetime(current)
        if candidate not in occupied:
            available_slots.append(candidate)
        current += timedelta(hours=1)

    return available_slots


def list_user_appointments(user_id: int) -> FutureAppointmentsPayload:
    appointments = Appointment.objects.filter(
        user_id=user_id,
        time_slot__gte=timezone.now(),
    ).order_by('time_slot', 'id')
    return _format_future_appointments_payload(list(appointments))


def book_appointment(
    user_id: int,
    time_slot: str,
    rrule_str: str | None = None,
    symptoms_summary: str = '',
    appointment_reason: str = '',
) -> Appointment:
    user_model = get_user_model()
    user = user_model.objects.get(id=user_id)
    parsed_time_slot = _parse_datetime_input(time_slot)

    return Appointment.objects.create(
        user=user,
        title='Booked Appointment',
        time_slot=parsed_time_slot,
        rrule=rrule_str or 'FREQ=DAILY;COUNT=1',
        symptoms_summary=symptoms_summary.strip(),
        appointment_reason=appointment_reason.strip(),
    )


def cancel_user_appointment(user_id: int, appointment_id: int) -> CancelAppointmentResult:
    deleted_count, _ = Appointment.objects.filter(
        id=appointment_id,
        user_id=user_id,
    ).delete()
    return {
        'appointment_id': appointment_id,
        'cancelled': deleted_count > 0,
    }


def update_user_appointment(
    user_id: int,
    appointment_id: int,
    time_slot: str | None = None,
    rrule_str: str | None = None,
    symptoms_summary: str | None = None,
    appointment_reason: str | None = None,
) -> UpdateAppointmentResult:
    appointment = Appointment.objects.filter(id=appointment_id, user_id=user_id).first()

    if appointment is None:
        return {
            'appointment_id': appointment_id,
            'updated': False,
            'reason': 'not_found',
        }

    if time_slot is not None:
        appointment.time_slot = _parse_datetime_input(time_slot)

    if rrule_str is not None:
        appointment.rrule = rrule_str

    if symptoms_summary is not None:
        appointment.symptoms_summary = symptoms_summary.strip()

    if appointment_reason is not None:
        appointment.appointment_reason = appointment_reason.strip()

    appointment.save(
        update_fields=['time_slot', 'rrule', 'symptoms_summary', 'appointment_reason']
    )

    return {
        'appointment_id': _appointment_id(appointment),
        'updated': True,
        'appointment': _serialize_appointment(appointment),
    }
