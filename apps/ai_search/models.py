from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class AISearchQuery(models.Model):
    """Historique des recherches IA avec suggestions"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_searches')
    query = models.TextField()
    response = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]


class AISearchSuggestion(models.Model):
    """Suggestions automatiques basés sur l'historique"""
    
    query = models.CharField(max_length=255)
    suggestion = models.TextField()
    frequency = models.PositiveIntegerField(default=0)
    last_used = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-frequency', '-last_used']
        indexes = [
            models.Index(fields=['query']),
            models.Index(fields=['-frequency']),
        ]
