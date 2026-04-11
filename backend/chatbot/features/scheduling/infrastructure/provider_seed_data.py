from datetime import UTC, datetime

PROVIDER_SEED_DATA = [
    {
        'name': 'Dr. Sarah Chen',
        'specialty': 'General Practice',
        'availability_dtstart': datetime(2026, 1, 5, 9, 0, 0, tzinfo=UTC),
        'availability_rrule': (
            'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR;'
            'BYHOUR=9,10,11,12,13,14,15,16;BYMINUTE=0;BYSECOND=0'
        ),
    },
    {
        'name': 'Dr. Marcus Rivera',
        'specialty': 'Internal Medicine',
        'availability_dtstart': datetime(2026, 1, 5, 8, 0, 0, tzinfo=UTC),
        'availability_rrule': (
            'FREQ=WEEKLY;BYDAY=MO,WE,FR;'
            'BYHOUR=8,9,10,11,12,13,14,15;BYMINUTE=0;BYSECOND=0'
        ),
    },
    {
        'name': 'Dr. Priya Nair',
        'specialty': 'Pediatrics',
        'availability_dtstart': datetime(2026, 1, 6, 10, 0, 0, tzinfo=UTC),
        'availability_rrule': (
            'FREQ=WEEKLY;BYDAY=TU,TH;'
            'BYHOUR=10,11,12,13,14,15,16,17;BYMINUTE=0;BYSECOND=0'
        ),
    },
    {
        'name': 'Dr. James Okafor',
        'specialty': 'Cardiology',
        'availability_dtstart': datetime(2026, 1, 5, 7, 0, 0, tzinfo=UTC),
        'availability_rrule': (
            'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH;'
            'BYHOUR=7,8,9,10,11,12,13,14;BYMINUTE=0;BYSECOND=0'
        ),
    },
    {
        'name': 'Dr. Elena Vasquez',
        'specialty': 'Urgent Care',
        'availability_dtstart': datetime(2026, 1, 5, 8, 0, 0, tzinfo=UTC),
        'availability_rrule': (
            'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA,SU;'
            'BYHOUR=8,9,10,11,12,13,14,15,16,17,18,19;BYMINUTE=0;BYSECOND=0'
        ),
    },
]
