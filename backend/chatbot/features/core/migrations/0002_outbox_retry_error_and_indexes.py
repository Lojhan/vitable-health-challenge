from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='outboxmessage',
            name='retry_count',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='outboxmessage',
            name='error',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddIndex(
            model_name='outboxmessage',
            index=models.Index(fields=['published_at', 'id'], name='core_outbox_publish_6a3279_idx'),
        ),
    ]
