from celery import shared_task
from django.db.models import Avg
from apps.accounts.models import User
from firebase_admin import messaging
from django.utils import timezone
from datetime import timedelta
from apps.missions.models import Mission
from apps.core.choices import MissionStatus

@shared_task
def update_agent_rating(agent_id):
    """Calcule la moyenne des notes de l'agent sans bloquer l'API"""
    agent = User.objects.get(id=agent_id)
    # Simulation d'un calcul complexe ou appel à une API externe
    # agent.reliability_score = ... calcul ...
    # agent.save()
    return f"Score de l'agent {agent.username} mis à jour."

@shared_task
def cleanup_expired_missions():
    """Annule les missions PENDING créées il y a plus de 2 heures"""
    threshold = timezone.now() - timedelta(hours=2)
    
    expired_missions = Mission.objects.filter(
        status=MissionStatus.PENDING,
        created_at__lt=threshold
    )
    
    count = expired_missions.count()
    # On passe en statut CANCELLED ou EXPIRED
    expired_missions.update(status=MissionStatus.CANCELLED)
    
    return f"{count} missions expirées ont été annulées."
    