# AUDIT FIX [P0] — Validators uploads missions
import apps.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0016_audit_mission_indexes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mission',
            name='description_audio',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='missions/voice/%Y/%m/%d/',
                validators=[apps.core.validators.validate_audio_upload],
                verbose_name='Description vocale (audio)',
            ),
        ),
        migrations.AlterField(
            model_name='mission',
            name='start_photo',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='missions/proofs/start/',
                validators=[apps.core.validators.validate_image_upload],
            ),
        ),
        migrations.AlterField(
            model_name='mission',
            name='end_photo',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='missions/proofs/end/',
                validators=[apps.core.validators.validate_image_upload],
            ),
        ),
    ]
