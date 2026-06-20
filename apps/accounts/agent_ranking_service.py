"""Service de calcul du score de classement des agents."""

from decimal import Decimal
from django.db import models
from apps.accounts.models import AgentProfile


class AgentRankingService:
    """Service pour calculer et mettre à jour le score de classement des agents.
    
    Formule pondérée :
    - 40% note moyenne (average_rating / 5 * 40)
    - 30% taux de complétion (completion_rate * 0.3)
    - 20% rapidité de réponse (inverse du temps, normalisé)
    - 10% volume de missions (logarithmique pour éviter biais)
    """

    @staticmethod
    def calculate_ranking_score(profile: AgentProfile) -> float:
        """Calcule le score de classement pour un agent (0-100)."""
        
        # 1. Note moyenne (40%)
        # Normalisé sur 0-5, puis sur 0-40
        rating_score = (float(profile.average_rating or 0) / 5.0) * 40.0
        
        # 2. Taux de complétion (30%)
        # Déjà en pourcentage 0-100
        completion_score = (profile.completion_rate or 0.0) * 0.3
        
        # 3. Rapidité de réponse (20%)
        # Temps moyen en secondes. Plus c'est bas, mieux c'est.
        # On considère 300 secondes (5 min) comme excellent, 3600 (1h) comme mauvais.
        response_time = profile.response_time_avg or 0.0
        if response_time > 0:
            # Inverse : 300s = 20 points, 3600s = 0 points
            response_score = max(0, 20.0 - ((response_time - 300) / 3300) * 20.0)
        else:
            response_score = 0.0  # Pas de données = 0
        
        # 4. Volume de missions (10%)
        # Logarithmique pour éviter biais : 1 mission = 1 point, 100 missions = ~10 points
        missions_count = profile.ratings_count or 0  # Utilisation de ratings_count comme proxy
        if missions_count > 0:
            volume_score = min(10.0, (missions_count ** 0.5))
        else:
            volume_score = 0.0
        
        # Score total
        total_score = rating_score + completion_score + response_score + volume_score
        
        # Clamp entre 0 et 100
        return max(0.0, min(100.0, total_score))

    @staticmethod
    def update_agent_ranking(agent_id):
        """Met à jour le score de classement d'un agent."""
        try:
            profile = AgentProfile.objects.select_related('user').get(user_id=agent_id)
            profile.ranking_score = AgentRankingService.calculate_ranking_score(profile)
            profile.save(update_fields=['ranking_score', 'updated_at'])
        except AgentProfile.DoesNotExist:
            pass

    @staticmethod
    def get_top_agents(limit: int = 10) -> list:
        """Retourne les agents classés par score de classement."""
        return AgentProfile.objects.filter(
            user__is_agent=True,
            kyc_status='APPROVED',
        ).select_related('user').order_by('-ranking_score')[:limit]

    @staticmethod
    def recalculate_all():
        """Recalcule tous les scores de classement (batch job)."""
        profiles = AgentProfile.objects.filter(user__is_agent=True)
        for profile in profiles:
            profile.ranking_score = AgentRankingService.calculate_ranking_score(profile)
        
        # Bulk update
        AgentProfile.objects.bulk_update(
            profiles,
            ['ranking_score'],
            batch_size=100
        )
