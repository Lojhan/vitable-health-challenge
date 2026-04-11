from django.db import migrations


def seed_providers_data():
    """Load provider seed data from centralized location.
    
    This indirection ensures reference data is defined in one place:
    chatbot/features/scheduling/infrastructure/provider_seed_data.py
    """
    try:
        from chatbot.features.scheduling.infrastructure.provider_seed_data import PROVIDER_SEED_DATA
        return PROVIDER_SEED_DATA
    except ImportError:
        # Fallback for migration isolation: if the infrastructure module
        # is not available, return hardcoded data
        from datetime import datetime
        from datetime import timezone as dt_timezone
        return [
            {
                'name': 'Dr. Sarah Chen',
                'specialty': 'General Practice',
                'availability_dtstart': datetime(2026, 1, 5, 9, 0, 0, tzinfo=dt_timezone.utc),
                'availability_rrule': (
                    'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR;'
                    'BYHOUR=9,10,11,12,13,14,15,16;BYMINUTE=0;BYSECOND=0'
                ),
            },
            {
                'name': 'Dr. Marcus Rivera',
                'specialty': 'Internal Medicine',
                'availability_dtstart': datetime(2026, 1, 5, 8, 0, 0, tzinfo=dt_timezone.utc),
                'availability_rrule': (
                    'FREQ=WEEKLY;BYDAY=MO,WE,FR;'
                    'BYHOUR=8,9,10,11,12,13,14,15;BYMINUTE=0;BYSECOND=0'
                ),
            },
            {
                'name': 'Dr. Priya Nair',
                'specialty': 'Pediatrics',
                'availability_dtstart': datetime(2026, 1, 6, 10, 0, 0, tzinfo=dt_timezone.utc),
                'availability_rrule': (
                    'FREQ=WEEKLY;BYDAY=TU,TH;'
                    'BYHOUR=10,11,12,13,14,15,16,17;BYMINUTE=0;BYSECOND=0'
                ),
            },
            {
                'name': 'Dr. James Okafor',
                'specialty': 'Cardiology',
                'availability_dtstart': datetime(2026, 1, 5, 7, 0, 0, tzinfo=dt_timezone.utc),
                'availability_rrule': (
                    'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH;'
                    'BYHOUR=7,8,9,10,11,12,13,14;BYMINUTE=0;BYSECOND=0'
                ),
            },
            {
                'name': 'Dr. Elena Vasquez',
                'specialty': 'Urgent Care',
                'availability_dtstart': datetime(2026, 1, 5, 8, 0, 0, tzinfo=dt_timezone.utc),
                'availability_rrule': (
                    'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA,SU;'
                    'BYHOUR=8,9,10,11,12,13,14,15,16,17,18,19;BYMINUTE=0;BYSECOND=0'
                ),
            },
        ]


def seed_providers(apps, schema_editor):
    """Seed provider reference data from centralized source."""
    Provider = apps.get_model('scheduling', 'Provider')
    providers_data = seed_providers_data()
    for data in providers_data:
        Provider.objects.get_or_create(name=data['name'], defaults={
            'specialty': data['specialty'],
            'availability_dtstart': data['availability_dtstart'],
            'availability_rrule': data['availability_rrule'],
        })


def unseed_providers(apps, schema_editor):
    """Remove seeded providers (reverting migration)."""
    Provider = apps.get_model('scheduling', 'Provider')
    providers_data = seed_providers_data()
    Provider.objects.filter(name__in=[p['name'] for p in providers_data]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0005_provider_model'),
    ]

    operations = [
        migrations.RunPython(seed_providers, reverse_code=unseed_providers),
    ]
