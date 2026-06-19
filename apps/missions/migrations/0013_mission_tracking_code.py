from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0012_remove_mission_requires_procuration'),
    ]

    operations = [
        migrations.AddField(
            model_name='mission',
            name='tracking_code',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Code de suivi public (ex: FNC-4829-BJ)',
                max_length=20,
                null=True,
                unique=True,
            ),
        ),
    ]
