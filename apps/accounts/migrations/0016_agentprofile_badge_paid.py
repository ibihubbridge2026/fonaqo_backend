from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0015_agent_code_internal_badge'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentprofile',
            name='badge_paid',
            field=models.BooleanField(
                default=False,
                help_text='1 000 FCFA unique prélevés au moment de la première demande de badge',
                verbose_name='frais badge payés',
            ),
        ),
    ]
