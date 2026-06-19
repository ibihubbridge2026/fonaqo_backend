from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_initial'),
        ('accounts', '0008_agentprofile_bio'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='payment',
            name='purpose',
            field=models.CharField(
                choices=[
                    ('wallet_deposit', 'Recharge portefeuille'),
                    ('boost_purchase', 'Achat boost'),
                    ('mission_payment', 'Paiement mission'),
                ],
                default='wallet_deposit',
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name='payment',
            name='amount',
            field=models.DecimalField(decimal_places=0, max_digits=12),
        ),
    ]
