from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0006_seed_providers'),
    ]

    operations = [
        migrations.AlterField(
            model_name='provider',
            name='name',
            field=models.CharField(max_length=200, unique=True),
        ),
    ]
