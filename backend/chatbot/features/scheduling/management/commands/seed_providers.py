from typing import Any

from django.core.management.base import BaseCommand

from chatbot.features.scheduling.infrastructure.provider_seed_data import PROVIDER_SEED_DATA
from chatbot.features.scheduling.models import Provider


class Command(BaseCommand):
    help = 'Seed or update default provider reference data'

    def handle(self, *args: Any, **options: Any) -> None:
        created_count = 0
        updated_count = 0

        for provider_data in PROVIDER_SEED_DATA:
            provider, created = Provider.objects.update_or_create(
                name=provider_data['name'],
                defaults={
                    'specialty': provider_data['specialty'],
                    'availability_dtstart': provider_data['availability_dtstart'],
                    'availability_rrule': provider_data['availability_rrule'],
                },
            )
            _ = provider
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Seeded providers complete: created={created_count}, updated={updated_count}'
            )
        )
