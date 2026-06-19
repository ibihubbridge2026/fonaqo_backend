# Generated manually for agent code, internal flag and professional badge

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0014_kyc_support_password_reset'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentprofile',
            name='agent_code',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text='Format AGT-00001',
                max_length=16,
                unique=True,
                verbose_name='identifiant agent',
            ),
        ),
        migrations.AddField(
            model_name='agentprofile',
            name='is_internal',
            field=models.BooleanField(
                default=False,
                help_text='Priorité suggestions client + badge certifié',
                verbose_name='agent interne',
            ),
        ),
        migrations.AddField(
            model_name='agentprofile',
            name='badge_status',
            field=models.CharField(
                choices=[
                    ('NONE', 'Aucune demande'),
                    ('PENDING', 'En attente validation'),
                    ('APPROVED', 'Badge approuvé'),
                    ('REJECTED', 'Demande rejetée'),
                ],
                default='NONE',
                max_length=20,
                verbose_name='statut badge professionnel',
            ),
        ),
        migrations.AddField(
            model_name='agentprofile',
            name='badge_photo',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='badges/photos/',
                verbose_name='photo badge professionnel',
            ),
        ),
        migrations.AddField(
            model_name='agentprofile',
            name='badge_requested_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='agentprofile',
            name='badge_approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='agentprofile',
            name='badge_rejection_reason',
            field=models.TextField(
                blank=True,
                default='',
                verbose_name='motif rejet badge',
            ),
        ),
    ]
