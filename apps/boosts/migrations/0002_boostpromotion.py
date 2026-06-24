from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('boosts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='BoostPromotion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('discount_percentage', models.PositiveIntegerField(help_text='Valeur entre 0 et 100', verbose_name='Pourcentage de réduction')),
                ('start_date', models.DateTimeField(verbose_name='Date de début')),
                ('end_date', models.DateTimeField(verbose_name='Date de fin')),
                ('is_active', models.BooleanField(default=True, verbose_name='Actif')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Date de création')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Date de modification')),
                ('boost_plan', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='promotions',
                    to='boosts.boostplan',
                    verbose_name='Plan de boost',
                )),
            ],
            options={
                'verbose_name': 'Promotion Boost',
                'verbose_name_plural': 'Promotions Boost',
                'ordering': ['-start_date'],
            },
        ),
    ]
