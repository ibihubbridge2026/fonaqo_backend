import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_user_service_domain'),
    ]

    operations = [
        migrations.CreateModel(
            name='AgentProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kyc_status', models.CharField(
                    choices=[('PENDING', 'En attente'), ('APPROVED', 'Approuve'), ('REJECTED', 'Rejete')],
                    default='PENDING',
                    max_length=20,
                )),
                ('id_card_photo', models.ImageField(blank=True, null=True, upload_to='kyc/agent_ids/', verbose_name="photo recto pièce d'identité")),
                ('selfie_photo', models.ImageField(blank=True, null=True, upload_to='kyc/agent_selfies/', verbose_name='selfie avec pièce')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='agent_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'profil agent',
                'verbose_name_plural': 'profils agents',
            },
        ),
    ]
