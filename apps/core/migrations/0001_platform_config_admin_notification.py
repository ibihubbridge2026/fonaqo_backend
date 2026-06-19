# Generated manually — platform config + admin notifications

from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


def seed_default_fees(apps, schema_editor):
    PlatformConfiguration = apps.get_model('core', 'PlatformConfiguration')
    defaults = [
        ('FEES_URGENT', '500', 'Supplément mission urgente (FCFA)'),
        ('FEES_CONFIDENTIAL', '500', 'Supplément agent interne Fonaqo (FCFA)'),
    ]
    for key, value, description in defaults:
        PlatformConfiguration.objects.get_or_create(
            key=key,
            defaults={'value': value, 'description': description},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0012_remove_mission_requires_procuration'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformConfiguration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(db_index=True, max_length=100, unique=True)),
                ('value', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'configuration plateforme',
                'verbose_name_plural': 'configurations plateforme',
                'ordering': ['key'],
            },
        ),
        migrations.CreateModel(
            name='AdminNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('MISSION_UNASSIGNED', 'Mission non acceptée'), ('DISPUTE', 'Litige'), ('SECURITY', 'Sécurité'), ('SYSTEM', 'Système')], max_length=30)),
                ('severity', models.CharField(choices=[('info', 'Info'), ('warning', 'Avertissement'), ('critical', 'Critique')], default='warning', max_length=10)),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('is_read', models.BooleanField(default=False)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('mission', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='admin_notifications', to='missions.mission')),
            ],
            options={
                'verbose_name': 'notification admin',
                'verbose_name_plural': 'notifications admin',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='adminnotification',
            index=models.Index(fields=['is_read', '-created_at'], name='core_adminn_is_read_idx'),
        ),
        migrations.AddIndex(
            model_name='adminnotification',
            index=models.Index(fields=['category', '-created_at'], name='core_adminn_categor_idx'),
        ),
        migrations.RunPython(seed_default_fees, migrations.RunPython.noop),
    ]
