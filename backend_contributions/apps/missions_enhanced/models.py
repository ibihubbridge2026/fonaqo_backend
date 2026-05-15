from django.db import models
from django.conf import settings

class MissionProof(models.Model):
    """
    Preuves photo multiples pour une mission
    Permet à l'agent de télécharger plusieurs photos comme preuve
    """
    mission = models.ForeignKey(
        'missions.Mission',
        on_delete=models.CASCADE,
        related_name='proofs'
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_proofs'
    )

    image = models.ImageField(
        upload_to='missions/proofs/%Y/%m/%d/',
        verbose_name="Photo preuve"
    )

    caption = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Légende"
    )

    is_primary = models.BooleanField(
        default=False,
        help_text="Photo principale affichée en premier"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    location_lat = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Latitude"
    )
    location_lng = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Longitude"
    )

    class Meta:
        verbose_name = "Preuve Photo"
        verbose_name_plural = "Preuves Photos"
        ordering = ['-is_primary', '-created_at']

    def __str__(self):
        return f"Preuve pour mission {self.mission.id} - {self.created_at}"


class MissionTimelineEvent(models.Model):
    """
    Événements détaillés dans la timeline d'une mission
    Pour tracking précis avec timestamps
    """
    EVENT_TYPE_CHOICES = [
        ('created', 'Mission créée'),
        ('published', 'Mission publiée'),
        ('accepted', 'Mission acceptée'),
        ('agent_en_route', 'Agent en route'),
        ('agent_arrived', 'Agent arrivé sur place'),
        ('waiting', 'En attente'),
        ('in_progress', 'En cours de réalisation'),
        ('proofs_uploaded', 'Preuves téléchargées'),
        ('completed', 'Mission terminée'),
        ('validated', 'Mission validée par le client'),
        ('cancelled', 'Mission annulée'),
        ('disputed', 'Litige ouvert'),
    ]

    mission = models.ForeignKey(
        'missions.Mission',
        on_delete=models.CASCADE,
        related_name='timeline_events'
    )

    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES
    )

    occurred_at = models.DateTimeField(auto_now_add=True)

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mission_timeline_events'
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notes additionnelles"
    )

    location_lat = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Latitude"
    )
    location_lng = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Longitude"
    )

    metadata = models.JSONField(
        blank=True,
        null=True,
        help_text="Données supplémentaires au format JSON"
    )

    class Meta:
        verbose_name = "Événement Timeline"
        verbose_name_plural = "Événements Timeline"
        ordering = ['occurred_at']
        indexes = [
            models.Index(fields=['mission', '-occurred_at']),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} - Mission {self.mission.id}"


class AgentStatistics(models.Model):
    """
    Statistiques avancées pour les agents
    Calculées et mises à jour régulièrement
    """
    agent = models.OneToOneField(
        'accounts.AgentProfile',
        on_delete=models.CASCADE,
        related_name='detailed_statistics'
    )

    # Totaux carrière
    total_missions = models.IntegerField(default=0)
    completed_missions = models.IntegerField(default=0)
    cancelled_missions = models.IntegerField(default=0)
    
    # Revenus
    total_earnings = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00
    )
    current_month_earnings = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00
    )
    
    # Performance
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00
    )
    total_ratings = models.IntegerField(default=0)
    
    completion_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Pourcentage de missions complétées"
    )
    
    average_response_time = models.IntegerField(
        default=0,
        help_text="Temps de réponse moyen en secondes"
    )
    
    # Temps actif
    total_active_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00
    )
    
    # Litiges
    total_disputes = models.IntegerField(default=0)
    resolved_disputes = models.IntegerField(default=0)
    
    # Streaks
    current_streak_days = models.IntegerField(default=0)
    longest_streak_days = models.IntegerField(default=0)
    
    # Dernière mise à jour
    last_updated = models.DateTimeField(auto_now=True)
    last_mission_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Statistiques Agent"
        verbose_name_plural = "Statistiques Agents"

    def __str__(self):
        return f"Stats de {self.agent.user.username if self.agent and self.agent.user else 'Agent'}"

    @property
    def success_rate(self):
        """Taux de réussite"""
        if self.total_missions == 0:
            return 0
        return (self.completed_missions / self.total_missions) * 100

    @property
    def level(self):
        """Niveau de l'agent basé sur les performances"""
        if self.completed_missions >= 500 and self.average_rating >= 4.8:
            return 'Platinum'
        elif self.completed_missions >= 200 and self.average_rating >= 4.5:
            return 'Gold'
        elif self.completed_missions >= 50 and self.average_rating >= 4.0:
            return 'Silver'
        elif self.completed_missions >= 10:
            return 'Bronze'
        else:
            return 'Newcomer'
