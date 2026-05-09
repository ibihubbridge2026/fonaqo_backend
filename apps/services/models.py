from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Category(models.Model):
    name = models.CharField(max_length=100)
    icon = models.ImageField(upload_to='categories/icons/', null=True, blank=True)
    keywords = models.TextField(help_text="Mots clés pour l'IA (ex: SBEE, facture, électricité)")

    def __str__(self):
        return self.name

class AgentService(models.Model):
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='offered_services')
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    experience_years = models.PositiveIntegerField(default=0)
    successful_missions = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.title} by {self.agent.username}"