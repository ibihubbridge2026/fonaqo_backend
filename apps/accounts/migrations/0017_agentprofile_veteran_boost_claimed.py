from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0016_agentprofile_badge_paid'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentprofile',
            name='veteran_boost_claimed',
            field=models.BooleanField(
                default=False,
                help_text='Pass Boost Gratuit 3 jours octroyé automatiquement dès 21 missions COMPLETED',
                verbose_name='pass boost vétéran réclamé',
            ),
        ),
    ]
