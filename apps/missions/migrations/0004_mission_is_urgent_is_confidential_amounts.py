# Generated for FONACO: champs montants & options mission

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0003_mission_agent_comment_mission_agent_rating_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='mission',
            name='purchase_amount',
            field=models.DecimalField(decimal_places=2, default=0.00, help_text="Montant dédié aux achats, débloqué immédiatement vers l'agent à l'acceptation", max_digits=12),
        ),
        migrations.AddField(
            model_name='mission',
            name='service_amount',
            field=models.DecimalField(decimal_places=2, default=0.00, help_text='Frais de prestation conservés en séquestre jusqu\'à la fin de la mission', max_digits=12),
        ),
        migrations.AddField(
            model_name='mission',
            name='is_urgent',
            field=models.BooleanField(default=False, help_text='Mission urgente : agents notifiés en priorité (+500 FCFA)'),
        ),
        migrations.AddField(
            model_name='mission',
            name='is_confidential',
            field=models.BooleanField(default=False, help_text='Mission confidentielle : visible uniquement par les agents internes (+500 FCFA)'),
        ),
        migrations.AddField(
            model_name='mission',
            name='purchase_released',
            field=models.BooleanField(default=False, help_text="Indique si le montant des achats a déjà été transféré à l'agent"),
        ),
    ]
