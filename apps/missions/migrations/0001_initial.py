# Generated migration for missions app

from django.db import migrations, models
import django.db.models.deletion
import uuid
import django.contrib.gis.db.models as gis_models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
                ('slug', models.SlugField(unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='AgentLevel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(choices=[('BEGINNER', 'Débutant'), ('INTERMEDIATE', 'Intermédiaire'), ('EXPERT', 'Expert'), ('TOP_AGENT', 'Agent Elite')], max_length=50)),
                ('min_missions', models.PositiveIntegerField(default=0)),
                ('priority_boost', models.FloatField(default=1.0)),
            ],
        ),
        migrations.CreateModel(
            name='Mission',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField()),
                ('location', gis_models.PointField(srid=4326)),
                ('address', models.CharField(max_length=500)),
                ('price', models.DecimalField(decimal_places=2, max_digits=12)),
                ('service_fee', models.DecimalField(decimal_places=2, default=0.0, max_digits=12)),
                ('status', models.CharField(choices=[('PENDING', 'En attente'), ('ACCEPTED', 'Acceptée'), ('ON_THE_WAY', 'En route'), ('IN_PROGRESS', 'En cours'), ('COMPLETED', 'Terminée'), ('CANCELLED', 'Annulée')], default='PENDING', max_length=20)),
                ('qr_code_token', models.CharField(blank=True, max_length=100, unique=True)),
                ('qr_expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('agent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='missions_assigned', to='accounts.user')),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='missions_ordered', to='accounts.user')),
                ('tags', models.ManyToManyField(blank=True, to='missions.tag')),
            ],
        ),
        migrations.CreateModel(
            name='BoostPlan',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('duration_hours', models.PositiveIntegerField()),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('priority_score', models.FloatField(default=2.0)),
            ],
        ),
        migrations.CreateModel(
            name='AgentBoost',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('active_until', models.DateTimeField()),
                ('zone', gis_models.PolygonField(blank=True, null=True, srid=4326)),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.user')),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='missions.boostplan')),
            ],
        ),
        migrations.CreateModel(
            name='MissionProof',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('caption', models.CharField(blank=True, max_length=255, verbose_name='Légende')),
                ('is_primary', models.BooleanField(default=False, help_text='Photo principale affichée en premier')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('location_lat', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Latitude')),
                ('location_lng', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Longitude')),
                ('image', models.ImageField(upload_to='missions/proofs/%Y/%m/%d/', verbose_name='Photo preuve')),
                ('mission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='proofs', to='missions.mission')),
                ('uploaded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='uploaded_proofs', to='accounts.user')),
            ],
            options={
                'verbose_name': 'Preuve Photo',
                'verbose_name_plural': 'Preuves Photos',
                'ordering': ['-is_primary', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MissionTimelineEvent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('created', 'Mission créée'), ('published', 'Mission publiée'), ('accepted', 'Mission acceptée'), ('agent_en_route', 'Agent en route'), ('agent_arrived', 'Agent arrivé sur place'), ('waiting', 'En attente'), ('in_progress', 'En cours de réalisation'), ('proofs_uploaded', 'Preuves téléchargées'), ('completed', 'Mission terminée'), ('validated', 'Mission validée par le client'), ('cancelled', 'Mission annulée'), ('disputed', 'Litige ouvert')], max_length=20)),
                ('occurred_at', models.DateTimeField(auto_now_add=True)),
                ('notes', models.TextField(blank=True, null=True, verbose_name='Notes additionnelles')),
                ('location_lat', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Latitude')),
                ('location_lng', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Longitude')),
                ('metadata', models.JSONField(blank=True, null=True, help_text='Données supplémentaires au format JSON')),
                ('mission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timeline_events', to='missions.mission')),
                ('performed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mission_timeline_events', to='accounts.user')),
            ],
            options={
                'verbose_name': 'Événement Timeline',
                'verbose_name_plural': 'Événements Timeline',
                'ordering': ['occurred_at'],
            },
        ),
        migrations.CreateModel(
            name='AgentStatistics',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_missions', models.PositiveIntegerField(default=0)),
                ('completed_missions', models.PositiveIntegerField(default=0)),
                ('cancelled_missions', models.PositiveIntegerField(default=0)),
                ('total_earnings', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('average_rating', models.DecimalField(decimal_places=2, default=0, max_digits=3)),
                ('current_streak', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('agent', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='agent_statistics', to='accounts.user')),
            ],
            options={
                'verbose_name': 'Statistiques Agent',
                'verbose_name_plural': 'Statistiques Agents',
            },
        ),
    ]
