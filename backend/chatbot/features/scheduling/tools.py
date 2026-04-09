import re
from datetime import timedelta
from datetime import timezone as dt_timezone
from typing import Any, TypedDict, cast

from dateutil.parser import parse as parse_datetime
from dateutil.rrule import rrulestr
from django.contrib.auth import get_user_model
from django.db.models import DateTimeField
from django.utils import timezone

from chatbot.features.scheduling.models import Appointment, Provider


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


def _coerce_appointment_id(raw_value: object) -> int | None:
    if isinstance(raw_value, int):
        return raw_value

    if isinstance(raw_value, str):
        match = re.search(r'\d+', raw_value)
        if match is not None:
            return int(match.group(0))

    return None


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
    provider_id: int | None = cast(int, appointment.provider_id) if appointment.provider_id is not None else None
    provider_name: str | None = appointment.provider.name if appointment.provider_id is not None else None
    return {
        'appointment_id': _appointment_id(appointment),
        'title': appointment.title,
        'time_slot': _display_datetime(appointment.time_slot),
        'time_slot_human_utc': _display_human_datetime_utc(appointment.time_slot),
        'rrule': appointment.rrule,
        'symptoms_summary': appointment.symptoms_summary,
        'appointment_reason': appointment.appointment_reason,
        'provider_id': provider_id,
        'provider_name': provider_name,
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


def resolve_datetime_reference(datetime_reference: str) -> dict: # or -> ResolveDatetimeReferenceResult if TypedDict is defined globally
    now = timezone.now().astimezone(dt_timezone.utc)
    normalized_reference = datetime_reference.strip().lower()

    if not normalized_reference:
        return {
            'resolved': False,
            'reference': datetime_reference,
            'reason': 'empty_reference',
        }

    base_date = now.date()

    # Catch optional prefixes and full/abbreviated weekday names
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
            'monday': 0, 'mon': 0,
            'tuesday': 1, 'tue': 1,
            'wednesday': 2, 'wed': 2,
            'thursday': 3, 'thu': 3,
            'friday': 4, 'fri': 4,
            'saturday': 5, 'sat': 5,
            'sunday': 6, 'sun': 6,
        }
        requested_weekday = weekdays[day_str]
        days_ahead = (requested_weekday - now.weekday()) % 7

        # If today is Monday and the user explicitly said "next monday", jump 7 days ahead.
        # Otherwise, if it's 0, it means today, which is technically the "closest" Monday.
        if days_ahead == 0 and prefix == 'next':
            days_ahead = 7

        base_date = (now + timedelta(days=days_ahead)).date()

    # Strip the resolved tokens so dateutil doesn't get confused and drift the date
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

    resolved = _normalize_datetime(resolved)
    return {
        'resolved': True,
        'reference': datetime_reference,
        'iso_datetime_utc': _display_datetime(resolved),
        'resolved_from_now_utc': _display_datetime(now),
    }

def list_providers() -> list[ProviderSchema]:
    return [
        {'provider_id': cast(int, cast(Any, p).pk), 'name': p.name, 'specialty': p.specialty}
        for p in Provider.objects.all().order_by('name')
    ]


def check_availability(date_range_str: str, provider_id: int | None = None) -> list[str]:
    start, end = _resolve_date_range_input(date_range_str)

    if provider_id is not None:
        try:
            provider = Provider.objects.get(pk=provider_id)
        except Provider.DoesNotExist:
            return []

        provider_rule = rrulestr(
            provider.availability_rrule, dtstart=provider.availability_dtstart
        )
        available_provider_slots = {
            _display_datetime(_normalize_datetime(occ))
            for occ in provider_rule.between(start, end, inc=True)
        }

        occupied: set[str] = set()
        for appointment in Appointment.objects.filter(provider_id=provider_id):
            rule = rrulestr(appointment.rrule, dtstart=appointment.time_slot)
            for occurrence in rule.between(start, end, inc=True):
                occupied.add(_display_datetime(_normalize_datetime(occurrence)))

        return sorted(available_provider_slots - occupied)

    occupied_open: set[str] = set()
    for appointment in Appointment.objects.all():
        rule = rrulestr(appointment.rrule, dtstart=appointment.time_slot)
        for occurrence in rule.between(start, end, inc=True):
            normalized_occurrence = _normalize_datetime(occurrence)
            occupied_open.add(_display_datetime(normalized_occurrence))

    available_slots = []
    current = start
    while current < end:
        candidate = _display_datetime(current)
        if candidate not in occupied_open:
            available_slots.append(candidate)
        current += timedelta(hours=1)

    return available_slots


def list_user_appointments(user_id: int) -> FutureAppointmentsPayload:
    appointments = (
        Appointment.objects.select_related('provider')
        .filter(user_id=user_id, time_slot__gte=timezone.now())
        .order_by('time_slot', 'id')
    )
    return _format_future_appointments_payload(list(appointments))


def book_appointment(
    user_id: int,
    time_slot: str,
    rrule_str: str | None = None,
    symptoms_summary: str = '',
    appointment_reason: str = '',
    appointment_id: int | str | None = None,
    provider_id: int | None = None,
) -> Appointment:
    user_model = get_user_model()
    user = user_model.objects.get(id=user_id)
    parsed_time_slot = _parse_datetime_input(time_slot)

    resolved_provider: Provider | None = None
    if provider_id is not None:
        try:
            resolved_provider = Provider.objects.get(pk=provider_id)
        except Provider.DoesNotExist:
            raise ValueError(f'Provider {provider_id} does not exist')

        provider_rule = rrulestr(
            resolved_provider.availability_rrule,
            dtstart=resolved_provider.availability_dtstart,
        )
        if not provider_rule.between(parsed_time_slot, parsed_time_slot, inc=True):
            raise ValueError(
                f'Time slot is not within provider {resolved_provider.name} availability'
            )

        conflict_qs = Appointment.objects.filter(
            provider_id=provider_id, time_slot=parsed_time_slot
        )
        normalized_appointment_id_pre = _coerce_appointment_id(appointment_id)
        if normalized_appointment_id_pre is not None:
            conflict_qs = conflict_qs.exclude(id=normalized_appointment_id_pre)
        if conflict_qs.exists():
            raise ValueError(
                f'Provider {resolved_provider.name} is already booked at {time_slot}'
            )

    normalized_appointment_id = _coerce_appointment_id(appointment_id)
    if normalized_appointment_id is not None:
        existing = Appointment.objects.filter(id=normalized_appointment_id, user_id=user_id).first()
        if existing is not None:
            existing.time_slot = parsed_time_slot
            existing.rrule = rrule_str or existing.rrule
            existing.symptoms_summary = symptoms_summary.strip() or existing.symptoms_summary
            existing.appointment_reason = (
                appointment_reason.strip() or existing.appointment_reason
            )
            update_fields = ['time_slot', 'rrule', 'symptoms_summary', 'appointment_reason']
            if resolved_provider is not None:
                existing.provider = resolved_provider
                update_fields.append('provider')
            existing.save(update_fields=update_fields)
            return existing

    return Appointment.objects.create(
        user=user,
        title='Booked Appointment',
        time_slot=parsed_time_slot,
        rrule=rrule_str or 'FREQ=DAILY;COUNT=1',
        symptoms_summary=symptoms_summary.strip(),
        appointment_reason=appointment_reason.strip(),
        provider=resolved_provider,
    )


def cancel_user_appointment(
    user_id: int,
    appointment_id: int | str,
) -> CancelAppointmentResult:
    normalized_appointment_id = _coerce_appointment_id(appointment_id)
    if normalized_appointment_id is None:
        return {
            'appointment_id': -1,
            'cancelled': False,
        }

    deleted_count, _ = Appointment.objects.filter(
        id=normalized_appointment_id,
        user_id=user_id,
    ).delete()
    return {
        'appointment_id': normalized_appointment_id,
        'cancelled': deleted_count > 0,
    }


def update_user_appointment(
    user_id: int,
    appointment_id: int | str,
    time_slot: str | None = None,
    rrule_str: str | None = None,
    symptoms_summary: str | None = None,
    appointment_reason: str | None = None,
    provider_id: int | None = None,
) -> UpdateAppointmentResult:
    normalized_appointment_id = _coerce_appointment_id(appointment_id)
    if normalized_appointment_id is None:
        return {
            'appointment_id': -1,
            'updated': False,
            'reason': 'invalid_appointment_id',
        }

    appointment = (
        Appointment.objects.select_related('provider')
        .filter(id=normalized_appointment_id, user_id=user_id)
        .first()
    )

    if appointment is None:
        return {
            'appointment_id': normalized_appointment_id,
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

    update_fields: list[str] = ['time_slot', 'rrule', 'symptoms_summary', 'appointment_reason']

    if provider_id is not None:
        try:
            new_provider = Provider.objects.get(pk=provider_id)
        except Provider.DoesNotExist:
            return {
                'appointment_id': normalized_appointment_id,
                'updated': False,
                'reason': 'invalid_provider_id',
            }

        effective_slot = _normalize_datetime(appointment.time_slot)
        provider_rule = rrulestr(
            new_provider.availability_rrule, dtstart=new_provider.availability_dtstart
        )
        if not provider_rule.between(effective_slot, effective_slot, inc=True):
            raise ValueError(
                f'Time slot is not within provider {new_provider.name} availability'
            )

        appointment.provider = new_provider
        update_fields.append('provider')

    appointment.save(update_fields=update_fields)

    return {
        'appointment_id': _appointment_id(appointment),
        'updated': True,
        'appointment': _serialize_appointment(appointment),
    }
