from django.db import models
from django.conf import settings

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
