from datetime import datetime
from unittest.mock import patch

from django.utils import timezone

from chatbot.features.scheduling.tools import resolve_datetime_reference


def test_resolve_datetime_reference_handles_tomorrow_with_time():
    resolved = resolve_datetime_reference('tomorrow at 9:30 am')

    assert resolved.get('resolved') is True
    iso_datetime_utc = resolved.get('iso_datetime_utc')
    assert iso_datetime_utc is not None
    assert iso_datetime_utc.endswith('09:30:00')


def test_resolve_datetime_reference_next_monday_uses_next_week_anchor():
    frozen_now = timezone.make_aware(datetime.fromisoformat('2026-04-06T08:00:00'))

    with patch(
        'chatbot.features.scheduling.application.common.timezone.now',
        return_value=frozen_now,
    ):
        resolved = resolve_datetime_reference('next monday')

    assert resolved.get('resolved') is True
    assert resolved.get('iso_datetime_utc') == '2026-04-13T09:00:00'
