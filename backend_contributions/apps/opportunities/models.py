from django.db import models
from django.conf import settings

class Opportunity(models.Model):
    """Opportunité / Service proposé sur la plateforme"""
    CATEGORY_CHOICES = [
        ('banque', 'Banque'),
        ('livraison', 'Livraison'),
        ('entretien', 'Entretien'),
        ('electricite', 'Électricité'),
        ('bricolage', 'Bricolage'),
        ('menage', 'Ménage'),
        ('courses', 'Courses'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    location = models.CharField(max_length=200)
    price_range = models.CharField(max_length=100)  # Ex: "À partir de 5000 FCFA"
    image_url = models.URLField(blank=True, null=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=4.5)
    is_open = models.BooleanField(default=True)
    is_urgent = models.BooleanField(default=False)
    provider_name = models.CharField(max_length=200, blank=True)  # Nom du prestataire
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Opportunités'
    
    def __str__(self):
        return f"{self.title} - {self.get_category_display()}"
