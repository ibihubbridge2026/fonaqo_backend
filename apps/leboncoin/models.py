import uuid

from django.contrib.gis.db import models as gis_models
from django.db import models


class LocalListing(models.Model):
    """
    Fiche répertoriée sur la carte LeBonCoin :
    artisans experts, restaurants, commerces, bons plans locaux.
    """

    class Category(models.TextChoices):
        ARTISAN = 'artisan', 'Artisan expert'
        RESTAURANT = 'restaurant', 'Restaurant'
        SHOP = 'shop', 'Commerce'
        SERVICE = 'service', 'Service local'
        LEISURE = 'leisure', 'Loisir / sortie'
        OTHER = 'other', 'Autre'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
    )
    specialty = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)

    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, default='Cotonou')
    district = models.CharField(max_length=100, blank=True)
    location = gis_models.PointField(geography=True, null=True, blank=True)

    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    website_url = models.URLField(blank=True)

    photo = models.ImageField(upload_to='leboncoin/%Y/%m/', null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=4.0)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    opening_hours = models.JSONField(default=dict, blank=True)
    tags = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_featured', '-rating', 'name']
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['city', 'district']),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_category_display()})'
