from django.db import migrations, models


def backfill_message_kind(apps, schema_editor):
    _ = schema_editor
    chat_message_model = apps.get_model('chat', 'ChatMessage')
    chat_message_model.objects.filter(message_kind__isnull=True).update(message_kind='text')


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0003_chatmessage_request_id_and_idempotency'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='message_kind',
            field=models.CharField(
                choices=[
                    ('text', 'Text'),
                    ('providers', 'Providers'),
                    ('availability', 'Availability'),
                    ('appointments', 'Appointments'),
                    ('json', 'JSON'),
                ],
                default='text',
                max_length=32,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(backfill_message_kind, migrations.RunPython.noop),
    ]