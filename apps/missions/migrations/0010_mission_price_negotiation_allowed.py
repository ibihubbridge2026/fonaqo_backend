from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0009_alter_mission_status_alter_missiontimeline_status'),
        ('accounts', '0008_agentprofile_bio'),
    ]

    operations = [
        migrations.AddField(
            model_name='mission',
            name='price_negotiation_allowed',
            field=models.BooleanField(
                default=False,
                help_text="Le client autorise l'agent à proposer un nouveau tarif via le chat",
            ),
        ),
    ]
