# Generated manually for LeBonCoin initial schema

import uuid

import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='LocalListing',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('category', models.CharField(
                    choices=[
                        ('artisan', 'Artisan expert'),
                        ('restaurant', 'Restaurant'),
                        ('shop', 'Commerce'),
                        ('service', 'Service local'),
                        ('leisure', 'Loisir / sortie'),
                        ('other', 'Autre'),
                    ],
                    default='other',
                    max_length=20,
                )),
                ('specialty', models.CharField(blank=True, max_length=120)),
                ('description', models.TextField(blank=True)),
                ('address', models.CharField(blank=True, max_length=255)),
                ('city', models.CharField(default='Cotonou', max_length=100)),
                ('district', models.CharField(blank=True, max_length=100)),
                ('location', django.contrib.gis.db.models.fields.PointField(blank=True, geography=True, null=True, srid=4326)),
                ('phone', models.CharField(blank=True, max_length=30)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('website_url', models.URLField(blank=True)),
                ('photo', models.ImageField(blank=True, null=True, upload_to='leboncoin/%Y/%m/')),
                ('rating', models.DecimalField(decimal_places=2, default=4.0, max_digits=3)),
                ('is_featured', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('opening_hours', models.JSONField(blank=True, default=dict)),
                ('tags', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-is_featured', '-rating', 'name'],
                'indexes': [
                    models.Index(fields=['category', 'is_active'], name='leboncoin_l_categor_idx'),
                    models.Index(fields=['city', 'district'], name='leboncoin_l_city_di_idx'),
                ],
            },
        ),
    ]
