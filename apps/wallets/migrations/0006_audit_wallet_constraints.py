# AUDIT FIX [P1] — Contraintes CHECK balance >= 0 + index transactions
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wallets', '0005_payoutrequest_provider_transaction_id'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='wallet',
            constraint=models.CheckConstraint(
                condition=models.Q(balance__gte=0),
                name='check_wallet_balance_non_negative',
            ),
        ),
        migrations.AddConstraint(
            model_name='wallet',
            constraint=models.CheckConstraint(
                condition=models.Q(escrow_balance__gte=0),
                name='check_escrow_balance_non_negative',
            ),
        ),
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(
                fields=['wallet', '-created_at'],
                name='wallet_tx_wallet_date_idx',
            ),
        ),
    ]
