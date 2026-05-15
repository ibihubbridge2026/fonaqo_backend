from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

User = get_user_model()


class Opportunity(models.Model):
    """Modèle pour les opportunités professionnelles"""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée'),
        ('expired', 'Expirée'),
    ]
    
    TYPE_CHOICES = [
        ('delivery', 'Livraison'),
        ('service', 'Service'),
        ('transport', 'Transport'),
        ('assistance', 'Assistance'),
        ('other', 'Autre'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Basse'),
        ('medium', 'Moyenne'),
        ('high', 'Haute'),
        ('urgent', 'Urgente'),
    ]
    
    title = models.CharField(max_length=255)
    description = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='other')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Localisation
    pickup_address = models.TextField()
    pickup_latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    pickup_longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    
    delivery_address = models.TextField(blank=True)
    delivery_latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    delivery_longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    
    # Budget et rémunération
    budget_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    budget_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fixed_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Délais
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    estimated_duration = models.DurationField(null=True, blank=True)  # Temps estimé
    
    # Client et agent
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='opportunities')
    assigned_agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_opportunities')
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Compétences requises
    required_skills = models.JSONField(default=list, blank=True)
    
    # Notes et feedback
    client_notes = models.TextField(blank=True)
    agent_feedback = models.TextField(blank=True)
    rating = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['type', 'priority']),
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['assigned_agent', '-created_at']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"
    
    @property
    def is_expired(self):
        """Vérifie si l'opportunité est expirée"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def can_be_assigned(self):
        """Vérifie si l'opportunité peut être assignée"""
        return self.status == 'active' and not self.is_expired and not self.assigned_agent
    
    @property
    def estimated_price(self):
        """Retourne le prix estimé (fixe ou moyenne du budget)"""
        if self.fixed_price:
            return self.fixed_price
        elif self.budget_min and self.budget_max:
            return (self.budget_min + self.budget_max) / 2
        elif self.budget_min:
            return self.budget_min
        elif self.budget_max:
            return self.budget_max
        return None


class OpportunityApplication(models.Model):
    """Candidatures pour les opportunités"""
    
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('accepted', 'Acceptée'),
        ('rejected', 'Refusée'),
        ('withdrawn', 'Retirée'),
    ]
    
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name='applications')
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='opportunity_applications')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    message = models.TextField(blank=True)  # Message de motivation
    proposed_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['opportunity', 'agent']
        indexes = [
            models.Index(fields=['opportunity', 'status']),
            models.Index(fields=['agent', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.agent.username} - {self.opportunity.title}"


class OpportunityMatch(models.Model):
    """Matching intelligent entre agents et opportunités"""
    
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name='matches')
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='opportunity_matches')
    
    # Score de matching (0-100)
    match_score = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Facteurs de matching
    distance_score = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    skills_score = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    availability_score = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    rating_score = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-match_score']
        unique_together = ['opportunity', 'agent']
        indexes = [
            models.Index(fields=['opportunity', '-match_score']),
            models.Index(fields=['agent', '-match_score']),
            models.Index(fields=['-match_score']),
        ]
    
    def __str__(self):
        return f"Match {self.match_score}% - {self.agent.username} ↔ {self.opportunity.title}"
