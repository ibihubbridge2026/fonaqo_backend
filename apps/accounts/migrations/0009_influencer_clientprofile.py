import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_agentprofile_bio'),
    ]

    operations = [
        migrations.CreateModel(
            name='Influencer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, verbose_name='nom')),
                ('code_promo', models.CharField(db_index=True, max_length=50, unique=True, verbose_name='code promo')),
                ('commission_rate', models.DecimalField(decimal_places=4, default=Decimal('0.02'), help_text='Part du montant brut mission (ex: 0.02 = 2 %)', max_digits=5, verbose_name='taux de commission')),
                ('duration_years', models.PositiveIntegerField(default=2, verbose_name='durée du contrat (années)')),
                ('earnings_balance', models.DecimalField(decimal_places=0, default=0, max_digits=12, verbose_name='solde commissions')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'influenceur',
                'verbose_name_plural': 'influenceurs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ClientProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('influencer_linked_at', models.DateTimeField(blank=True, null=True, verbose_name='date liaison influenceur')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('influencer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='clients', to='accounts.influencer')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='client_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'profil client',
                'verbose_name_plural': 'profils clients',
            },
        ),
    ]
