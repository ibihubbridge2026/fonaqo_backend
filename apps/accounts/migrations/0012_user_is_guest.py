import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_alter_clientprofile_referral_code_cache_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_guest',
            field=models.BooleanField(
                default=False,
                help_text='Créé via le parcours web sans application mobile',
                verbose_name='compte invité (web vitrine)',
            ),
        ),
    ]
