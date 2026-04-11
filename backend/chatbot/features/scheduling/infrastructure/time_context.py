from datetime import UTC, datetime, timedelta


def build_temporal_anchor_lines(now_utc: datetime | None = None) -> str:
    resolved_now_utc = (now_utc or datetime.now(UTC)).astimezone(UTC)

    anchor_today = resolved_now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    anchor_tomorrow = anchor_today + timedelta(days=1)
    anchor_day_after_tomorrow = anchor_today + timedelta(days=2)
    anchor_next_week = anchor_today + timedelta(days=7)
    anchor_in_two_weeks = anchor_today + timedelta(days=14)
    anchor_other_week = anchor_today - timedelta(days=7)
    anchor_in_a_month = anchor_today + timedelta(days=30)

    return (
        'TEMPORAL ANCHORS (pre-calculated UTC datetimes, use these exact anchors before tool calls):\n'
        f'- today: {anchor_today.isoformat()}\n'
        f'- tomorrow: {anchor_tomorrow.isoformat()}\n'
        f'- the day after tomorrow: {anchor_day_after_tomorrow.isoformat()}\n'
        f'- next week: {anchor_next_week.isoformat()}\n'
        f'- in two weeks: {anchor_in_two_weeks.isoformat()}\n'
        f'- the other week (past context only): {anchor_other_week.isoformat()}\n'
        f'- in a month: {anchor_in_a_month.isoformat()}\n'
        'Combine anchor date with explicit user-provided time when available.\n\n'
    )
