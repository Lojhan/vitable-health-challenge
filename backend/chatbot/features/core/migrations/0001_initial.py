from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='OutboxMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('aggregate_type', models.CharField(max_length=120)),
                ('aggregate_id', models.CharField(max_length=64)),
                ('event_type', models.CharField(max_length=120)),
                ('payload', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={'ordering': ['id']},
        ),
    ]
