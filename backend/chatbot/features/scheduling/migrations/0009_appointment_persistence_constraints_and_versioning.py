from django.db import migrations, models


def backfill_appointment_constraints(apps, schema_editor):
    _ = schema_editor
    appointment_model = apps.get_model('scheduling', 'Appointment')

    # Normalize blank titles before enabling strict title constraint.
    appointment_model.objects.filter(title__regex=r'^\s*$').update(title='Booked Appointment')

    # Rollout-safe dedupe for provider + time_slot before unique constraint.
    seen_pairs: set[tuple[int, object]] = set()
    for appointment in appointment_model.objects.exclude(provider_id__isnull=True).order_by('id'):
        key = (appointment.provider_id, appointment.time_slot)
        if key in seen_pairs:
            appointment.delete()
            continue
        seen_pairs.add(key)


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0008_appointment_appointment_symptoms_summary_not_blank_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='appointment',
            name='version',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(backfill_appointment_constraints, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='appointment',
            constraint=models.CheckConstraint(
                condition=models.Q(('title__regex', '^\\s*$'), _negated=True),
                name='appointment_title_not_blank',
            ),
        ),
        migrations.AddConstraint(
            model_name='appointment',
            constraint=models.UniqueConstraint(
                condition=models.Q(('provider__isnull', True), _negated=True),
                fields=('provider', 'time_slot'),
                name='appointment_provider_timeslot_unique',
            ),
        ),
    ]
