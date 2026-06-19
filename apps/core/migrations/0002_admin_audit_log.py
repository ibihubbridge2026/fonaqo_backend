# Generated manually for AdminAuditLog

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0001_platform_config_admin_notification'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdminAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(db_index=True, max_length=80)),
                ('target_type', models.CharField(blank=True, default='', max_length=50)),
                ('target_id', models.CharField(blank=True, default='', max_length=64)),
                ('detail', models.TextField(blank=True, default='')),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('admin', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='admin_audit_logs',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'journal audit admin',
                'verbose_name_plural': 'journaux audit admin',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['action', '-created_at'], name='core_admina_action_0a8f2d_idx'),
                    models.Index(fields=['target_type', '-created_at'], name='core_admina_target__b4e1c9_idx'),
                ],
            },
        ),
    ]
