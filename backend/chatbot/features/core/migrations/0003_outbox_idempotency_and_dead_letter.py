from django.db import migrations, models


def backfill_outbox_idempotency_keys(apps, schema_editor):
    _ = schema_editor
    outbox_model = apps.get_model('core', 'OutboxMessage')
    for row in outbox_model.objects.all().only('id', 'aggregate_type', 'aggregate_id', 'event_type'):
        row.idempotency_key = (
            f'{row.aggregate_type}:{row.aggregate_id}:{row.event_type}:{row.id}'
        )
        row.save(update_fields=['idempotency_key'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_outbox_retry_error_and_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='outboxmessage',
            name='dead_lettered_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='outboxmessage',
            name='idempotency_key',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.RunPython(backfill_outbox_idempotency_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='outboxmessage',
            name='idempotency_key',
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.AddIndex(
            model_name='outboxmessage',
            index=models.Index(fields=['dead_lettered_at', 'id'], name='core_outbox_deadlet_e98f6f_idx'),
        ),
    ]
