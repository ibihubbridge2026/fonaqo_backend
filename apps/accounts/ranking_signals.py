"""Signaux Django pour la mise à jour automatique du score de classement des agents."""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.ratings.models import Rating
from apps.missions.models import Mission
from apps.accounts.agent_ranking_service import AgentRankingService


def _refresh_agent_completion_rate(agent):
    """Recalcule et persiste le taux de complétion réel de l'agent."""
    from apps.accounts.models import AgentProfile
    total = Mission.objects.filter(
        agent=agent,
        status__in=['COMPLETED', 'CANCELLED', 'DISPUTED'],
    ).count()
    completed = Mission.objects.filter(agent=agent, status='COMPLETED').count()
    rate = (completed / total * 100.0) if total > 0 else 0.0
    AgentProfile.objects.filter(user=agent).update(completion_rate=rate)


@receiver(post_save, sender=Rating)
@receiver(post_delete, sender=Rating)
def update_ranking_on_rating_change(sender, instance, **kwargs):
    """Met à jour le score de classement quand une note est ajoutée/supprimée."""
    if instance.reviewee and instance.reviewee.is_agent:
        _refresh_agent_average_rating(instance.reviewee)
        AgentRankingService.update_agent_ranking(instance.reviewee.id)


def _refresh_agent_average_rating(agent):
    """Recalcule et persiste la note moyenne de l'agent depuis les Rating."""
    from apps.accounts.models import AgentProfile
    from django.db.models import Avg, Count
    from apps.ratings.models import Rating as R
    agg = R.objects.filter(
        reviewee=agent,
        rating_type='CLIENT_RATES_AGENT',
    ).aggregate(avg=Avg('score'), cnt=Count('id'))
    avg = round(float(agg['avg'] or 0), 2)
    cnt = agg['cnt'] or 0
    AgentProfile.objects.filter(user=agent).update(
        average_rating=avg,
        ratings_count=cnt,
    )


@receiver(post_save, sender=Mission)
def update_ranking_on_mission_completion(sender, instance, created, **kwargs):
    """Met à jour completion_rate + ranking_score quand une mission se termine."""
    if not created and instance.agent and instance.agent.is_agent:
        if instance.status in ['COMPLETED', 'CANCELLED', 'DISPUTED']:
            _refresh_agent_completion_rate(instance.agent)
            AgentRankingService.update_agent_ranking(instance.agent.id)
