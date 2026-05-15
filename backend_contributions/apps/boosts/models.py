from django.db import models
from django.utils import timezone
from datetime import timedelta

# Note: Importer AgentProfile depuis apps.accounts.models lors de l'intégration
# from apps.accounts.models import AgentProfile

class BoostPlan(models.Model):
    """
    Plans de boost disponibles à l'achat
    Exemples: Day Boost, Week Boost, Month Boost
    """
    name = models.CharField(max_length=50, verbose_name="Nom du plan")
    duration_hours = models.IntegerField(verbose_name="Durée (heures)")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix (FCFA)")
    description = models.TextField(blank=True, verbose_name="Description")
    visibility_multiplier = models.DecimalField(
        max_digits=3, 
        decimal_places=1, 
        default=1.5,
        verbose_name="Multiplicateur de visibilité"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Date de modification")

    class Meta:
        verbose_name = "Plan de Boost"
        verbose_name_plural = "Plans de Boost"
        ordering = ['price']

    def __str__(self):
        return f"{self.name} - {self.price} FCFA ({self.duration_hours}h)"

    @property
    def duration_display(self):
        if self.duration_hours >= 24:
            days = self.duration_hours // 24
            return f"{days} jour(s)"
        return f"{self.duration_hours} heures"


class AgentBoost(models.Model):
    """
    Boosts actifs ou historiques pour un agent
    """
    STATUS_CHOICES = [
        ('active', 'Actif'),
        ('expired', 'Expiré'),
        ('cancelled', 'Annulé'),
    ]

    # Relation avec AgentProfile (à adapter selon votre modèle)
    # Décommenter et adapter lors de l'intégration
    # agent = models.ForeignKey(
    #     'accounts.AgentProfile', 
    #     on_delete=models.CASCADE, 
    #     related_name='boosts'
    # )
    
    # Temporaire pour développement
    agent_id = models.IntegerField(verbose_name="ID Agent")
    
    plan = models.ForeignKey(
        BoostPlan, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='boosts'
    )
    
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de début")
    expires_at = models.DateTimeField(verbose_name="Date d'expiration")
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='active',
        verbose_name="Statut"
    )
    
    purchase_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Montant payé (FCFA)"
    )
    
    transaction_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        verbose_name="ID Transaction"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        verbose_name = "Boost Agent"
        verbose_name_plural = "Boosts Agents"
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['agent_id', 'status']),
            models.Index(fields=['expires_at']),
        ]

    def save(self, *args, **kwargs):
        # Calcul automatique de la date d'expiration si non définie
        if not self.expires_at and self.plan:
            self.expires_at = self.started_at + timedelta(hours=self.plan.duration_hours)
        
        # Vérification automatique du statut
        if self.expires_at and timezone.now() > self.expires_at:
            self.status = 'expired'
            
        super().save(*args, **kwargs)

    @property
    def time_remaining_seconds(self):
        """Temps restant en secondes"""
        if self.status != 'active':
            return 0
        remaining = self.expires_at - timezone.now()
        return max(0, int(remaining.total_seconds()))

    @property
    def time_remaining_display(self):
        """Affichage humain du temps restant"""
        seconds = self.time_remaining_seconds
        if seconds == 0:
            return "Expiré"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        
        if hours > 24:
            days = hours // 24
            return f"{days}j {hours % 24}h"
        elif hours > 0:
            return f"{hours}h {minutes}min"
        else:
            return f"{minutes}min"

    @property
    def is_currently_active(self):
        """Vérifie si le boost est actuellement actif"""
        return self.status == 'active' and timezone.now() < self.expires_at

    def __str__(self):
        return f"Boost {self.plan.name if self.plan else 'Inconnu'} - Agent {self.agent_id}"
