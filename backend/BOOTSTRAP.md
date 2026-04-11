# Environment Bootstrap Guide

This document describes how to initialize the database and reference data for local, test, and production environments.

## Schema vs. Reference Data Lifecycle

- **Schema migrations** (in `chatbot/features/<feature>/migrations/`) define the database structure. They are applied via `manage.py migrate`.
- **Reference data** (providers, default settings, etc.) is managed separately via **management commands**. This keeps environment configuration decoupled from schema evolution.

## Local Development Setup

### 1. Create and Apply Database Schema

```bash
cd backend
../.venv/bin/python manage.py migrate
```

This creates all tables based on current schema migrations.

### 2. Seed Reference Data

```bash
../.venv/bin/python manage.py seed_providers
```

This populates the `scheduling.Provider` table with default provider data from `chatbot/features/scheduling/infrastructure/provider_seed_data.py`.

The `seed_providers` command is **idempotent**: running it multiple times is safe and will update existing providers or create new ones as needed.

### 3. (Optional) Create Superuser

```bash
../.venv/bin/python manage.py createsuperuser
```

## CI/Test Environment Setup

Tests do not automatically seed reference data. Before running integration tests that depend on providers:

```bash
../.venv/bin/python manage.py migrate --settings chatbot.settings
../.venv/bin/python manage.py seed_providers --settings chatbot.settings
../.venv/bin/pytest
```

See `test_seed_providers_management_command_is_idempotent()` in [test_models.py](chatbot/features/scheduling/tests/test_models.py) for an example.

## Production Deployment

1. Apply schema migrations:
   ```bash
   manage.py migrate
   ```

2. Seed or refresh provider data:
   ```bash
   manage.py seed_providers
   ```

3. The command uses `update_or_create()`, so it is safe to run multiple times or to update provider details.

## Reference Data Source Files

- **Provider seed data**: [`chatbot/features/scheduling/infrastructure/provider_seed_data.py`](chatbot/features/scheduling/infrastructure/provider_seed_data.py)
- **Bootstrap command**: [`chatbot/features/scheduling/management/commands/seed_providers.py`](chatbot/features/scheduling/management/commands/seed_providers.py)

## Adding New Reference Data Types

To add a new type of reference data (e.g., symptoms, insurance tiers):

1. Define the data in `chatbot/features/<feature>/infrastructure/<data_name>_seed_data.py`
2. Create a management command at `chatbot/features/<feature>/management/commands/seed_<data_name>.py`
3. Import and use the data file in your command for consistency
4. Document the new command in this file and in the command's `help` text

## Troubleshooting

### "Provider already exists" errors during `migrate`

Old migrations may have embedded seed code. To handle this safely:
- The new `0006_seed_providers.py` migration imports from the centralized data source
- For already-applied migrations, this change has no effect (migrations run once)
- Use `manage.py seed_providers` for all future reference data management

### Duplicate provider names

If you see integrity errors with duplicate provider names:
```bash
# View all providers
../.venv/bin/python manage.py shell
>>> from chatbot.features.scheduling.models import Provider
>>> Provider.objects.values_list('name', flat=True)

# Delete as needed
>>> Provider.objects.filter(name='Dr. Duplicate').delete()
```

Then re-run `seed_providers` if needed.
