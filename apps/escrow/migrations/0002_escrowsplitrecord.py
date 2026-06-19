# Generated manually for FONACO roadmap

import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_influencer_clientprofile'),
        ('missions', '0011_labor_material_withdrawal'),
        ('escrow', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EscrowSplitRecord',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('beneficiary_type', models.CharField(choices=[('AGENT', 'Agent'), ('PLATFORM', 'Plateforme FONACO'), ('INFLUENCER', 'Influenceur')], max_length=20)),
                ('amount_fcfa', models.DecimalField(decimal_places=2, max_digits=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('beneficiary_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='escrow_split_records', to=settings.AUTH_USER_MODEL)),
                ('influencer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='escrow_split_records', to='accounts.influencer')),
                ('mission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='escrow_split_records', to='missions.mission')),
            ],
            options={
                'verbose_name': 'écriture split escrow',
                'verbose_name_plural': 'écritures split escrow',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='escrowsplitrecord',
            index=models.Index(fields=['mission', '-created_at'], name='escrow_escr_mission_idx'),
        ),
        migrations.AddIndex(
            model_name='escrowsplitrecord',
            index=models.Index(fields=['beneficiary_type', '-created_at'], name='escrow_escr_benefic_idx'),
        ),
    ]
