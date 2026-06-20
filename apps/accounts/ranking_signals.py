"""Signaux Django pour la mise à jour automatique du score de classement des agents."""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.ratings.models import Rating
from apps.missions.models import Mission
from apps.accounts.agent_ranking_service import AgentRankingService


@receiver(post_save, sender=Rating)
@receiver(post_delete, sender=Rating)
def update_ranking_on_rating_change(sender, instance, **kwargs):
    """Met à jour le score de classement quand une note est ajoutée/supprimée."""
    # Recalculer pour l'agent noté (reviewee)
    if instance.reviewee and instance.reviewee.is_agent:
        AgentRankingService.update_agent_ranking(instance.reviewee.id)


@receiver(post_save, sender=Mission)
def update_ranking_on_mission_completion(sender, instance, created, **kwargs):
    """Met à jour le score de classement quand une mission est complétée ou annulée."""
    if not created and instance.agent and instance.agent.is_agent:
        # Mettre à jour si la mission change de statut
        if instance.status in ['COMPLETED', 'CANCELLED', 'DISPUTED']:
            AgentRankingService.update_agent_ranking(instance.agent.id)
