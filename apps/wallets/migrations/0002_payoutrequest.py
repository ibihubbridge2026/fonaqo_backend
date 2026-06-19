import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('wallets', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PayoutRequest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Montant')),
                ('payment_method', models.CharField(max_length=50, verbose_name='Opérateur MoMo')),
                ('phone_number', models.CharField(max_length=20, verbose_name='Numéro de versement')),
                ('status', models.CharField(
                    choices=[('PENDING', 'En attente'), ('COMPLETED', 'Valide'), ('REJECTED', 'Rejete')],
                    db_index=True,
                    default='PENDING',
                    max_length=20,
                )),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('rejection_reason', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ledger_transaction', models.OneToOneField(
                    blank=True,
                    help_text="Écriture comptable WITHDRAWAL créée à l'approbation",
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='payout_request',
                    to='wallets.transaction',
                )),
                ('processed_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='processed_payouts',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('wallet', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payout_requests',
                    to='wallets.wallet',
                )),
            ],
            options={
                'verbose_name': 'Demande de retrait',
                'verbose_name_plural': 'Demandes de retrait',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['status', '-created_at'], name='wallets_pay_status_idx'),
                ],
            },
        ),
    ]
