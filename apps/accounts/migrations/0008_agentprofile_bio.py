from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_agentprofile'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentprofile',
            name='bio',
            field=models.TextField(
                blank=True,
                help_text="Présentation publique de l'agent",
                null=True,
                verbose_name='biographie agent',
            ),
        ),
    ]
