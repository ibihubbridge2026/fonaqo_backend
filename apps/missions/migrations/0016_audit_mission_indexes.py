# AUDIT FIX [P1/P2] — Indexes manquants sur Mission
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0015_delete_missionrecommendation'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='mission',
            index=models.Index(
                fields=['target_agent_username'],
                name='mission_target_agent_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='mission',
            index=models.Index(
                fields=['status', 'agent', 'created_at'],
                name='mission_status_agent_date_idx',
            ),
        ),
    ]
