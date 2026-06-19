import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0009_influencer_clientprofile'),
    ]

    operations = [
        migrations.CreateModel(
            name='AgentStatistics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_missions', models.IntegerField(default=0)),
                ('completed_missions', models.IntegerField(default=0)),
                ('cancelled_missions', models.IntegerField(default=0)),
                ('total_earnings', models.DecimalField(decimal_places=2, default=0.0, max_digits=12)),
                ('current_month_earnings', models.DecimalField(decimal_places=2, default=0.0, max_digits=12)),
                ('average_rating', models.DecimalField(decimal_places=2, default=0.0, max_digits=3)),
                ('total_ratings', models.IntegerField(default=0)),
                ('completion_rate', models.DecimalField(decimal_places=2, default=0.0, help_text='Pourcentage de missions complétées', max_digits=5)),
                ('average_response_time', models.IntegerField(default=0, help_text='Temps de réponse moyen en secondes')),
                ('total_active_hours', models.DecimalField(decimal_places=2, default=0.0, max_digits=8)),
                ('total_disputes', models.IntegerField(default=0)),
                ('resolved_disputes', models.IntegerField(default=0)),
                ('current_streak_days', models.IntegerField(default=0)),
                ('longest_streak_days', models.IntegerField(default=0)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('last_mission_date', models.DateTimeField(blank=True, null=True)),
                ('agent', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='detailed_statistics', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Statistiques Agent',
                'verbose_name_plural': 'Statistiques Agents',
            },
        ),
    ]
