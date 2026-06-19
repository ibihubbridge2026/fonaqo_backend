from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0010_mission_price_negotiation_allowed'),
    ]

    operations = [
        migrations.AddField(
            model_name='mission',
            name='labor_cost',
            field=models.DecimalField(
                decimal_places=2,
                default=0.0,
                help_text="Montant main d'œuvre (séquestre jusqu'à complétion)",
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name='mission',
            name='material_cost',
            field=models.DecimalField(
                decimal_places=2,
                default=0.0,
                help_text='Montant matériel / fournitures (libéré sur validation admin)',
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name='mission',
            name='material_released',
            field=models.BooleanField(
                default=False,
                help_text='Indique si le montant matériel a été libéré à l\'agent',
            ),
        ),
        migrations.CreateModel(
            name='MaterialWithdrawalRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('status', models.CharField(
                    choices=[
                        ('PENDING', 'En attente'),
                        ('APPROVED', 'Approuvée'),
                        ('REJECTED', 'Rejetée'),
                    ],
                    default='PENDING',
                    max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('mission', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='material_withdrawal_requests',
                    to='missions.mission',
                )),
            ],
            options={
                'verbose_name': 'demande déblocage matériel',
                'verbose_name_plural': 'demandes déblocage matériel',
                'ordering': ['-created_at'],
            },
        ),
    ]
