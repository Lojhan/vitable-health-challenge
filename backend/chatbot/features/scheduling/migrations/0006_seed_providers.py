from datetime import datetime, timezone as dt_timezone

from django.db import migrations


PROVIDERS = [
    {
        'name': 'Dr. Sarah Chen',
        'specialty': 'General Practice',
        # Available Mon–Fri, 09:00–17:00 UTC (hourly slots)
        'availability_dtstart': datetime(2026, 1, 5, 9, 0, 0, tzinfo=dt_timezone.utc),
        'availability_rrule': (
            'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR;'
            'BYHOUR=9,10,11,12,13,14,15,16;BYMINUTE=0;BYSECOND=0'
        ),
    },
    {
        'name': 'Dr. Marcus Rivera',
        'specialty': 'Internal Medicine',
        # Available Mon/Wed/Fri, 08:00–16:00 UTC
        'availability_dtstart': datetime(2026, 1, 5, 8, 0, 0, tzinfo=dt_timezone.utc),
        'availability_rrule': (
            'FREQ=WEEKLY;BYDAY=MO,WE,FR;'
            'BYHOUR=8,9,10,11,12,13,14,15;BYMINUTE=0;BYSECOND=0'
        ),
    },
    {
        'name': 'Dr. Priya Nair',
        'specialty': 'Pediatrics',
        # Available Tue/Thu, 10:00–18:00 UTC
        'availability_dtstart': datetime(2026, 1, 6, 10, 0, 0, tzinfo=dt_timezone.utc),
        'availability_rrule': (
            'FREQ=WEEKLY;BYDAY=TU,TH;'
            'BYHOUR=10,11,12,13,14,15,16,17;BYMINUTE=0;BYSECOND=0'
        ),
    },
    {
        'name': 'Dr. James Okafor',
        'specialty': 'Cardiology',
        # Available Mon–Thu, 07:00–15:00 UTC
        'availability_dtstart': datetime(2026, 1, 5, 7, 0, 0, tzinfo=dt_timezone.utc),
        'availability_rrule': (
            'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH;'
            'BYHOUR=7,8,9,10,11,12,13,14;BYMINUTE=0;BYSECOND=0'
        ),
    },
    {
        'name': 'Dr. Elena Vasquez',
        'specialty': 'Urgent Care',
        # Available Mon–Sun, 08:00–20:00 UTC (urgent care hours)
        'availability_dtstart': datetime(2026, 1, 5, 8, 0, 0, tzinfo=dt_timezone.utc),
        'availability_rrule': (
            'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA,SU;'
            'BYHOUR=8,9,10,11,12,13,14,15,16,17,18,19;BYMINUTE=0;BYSECOND=0'
        ),
    },
]


def seed_providers(apps, schema_editor):
    Provider = apps.get_model('scheduling', 'Provider')
    for data in PROVIDERS:
        Provider.objects.get_or_create(name=data['name'], defaults={
            'specialty': data['specialty'],
            'availability_dtstart': data['availability_dtstart'],
            'availability_rrule': data['availability_rrule'],
        })


def unseed_providers(apps, schema_editor):
    Provider = apps.get_model('scheduling', 'Provider')
    Provider.objects.filter(name__in=[p['name'] for p in PROVIDERS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0005_provider_model'),
    ]

    operations = [
        migrations.RunPython(seed_providers, reverse_code=unseed_providers),
    ]
