from django.db import models
from django.conf import settings

class SearchQueryLog(models.Model):
    """Historique des recherches IA pour amélioration du modèle"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    query = models.TextField()
    user_type = models.CharField(max_length=10, choices=[('client', 'Client'), ('agent', 'Agent')])
    results_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user_type} - {self.query[:50]}"
