# Generated manually — referral deep link fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_influencer_clientprofile'),
    ]

    operations = [
        migrations.AddField(
            model_name='influencer',
            name='referral_slug',
            field=models.SlugField(
                blank=True,
                help_text='Slug deep link ex: INFLU_BENIN → fonaco.app/join/INFLU_BENIN',
                max_length=80,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name='clientprofile',
            name='referral_code_cache',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Code influenceur capturé via deep link avant inscription',
                max_length=80,
            ),
        ),
    ]
