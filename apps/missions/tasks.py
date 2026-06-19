import logging

from celery import shared_task
from django.utils import timezone

from apps.core.choices import MissionStatus
from apps.core.models import AdminNotification

logger = logging.getLogger(__name__)


@shared_task
def check_pending_mission_alert(mission_id: str):
    """
    Vérifie à T+5 min si une mission est toujours PENDING sans agent.
    Crée une AdminNotification pour le panel SuperAdmin.
    """
    from apps.missions.models import Mission

    try:
        mission = Mission.objects.select_related('client').get(pk=mission_id)
    except Mission.DoesNotExist:
        logger.warning('Mission %s introuvable pour alerte T+5', mission_id)
        return

    if mission.status != MissionStatus.PENDING or mission.agent_id is not None:
        return

    if AdminNotification.objects.filter(
        mission=mission,
        category=AdminNotification.Category.MISSION_UNASSIGNED,
    ).exists():
        return

    AdminNotification.objects.create(
        category=AdminNotification.Category.MISSION_UNASSIGNED,
        severity=AdminNotification.Severity.WARNING,
        title='Mission non acceptée après 5 minutes',
        message=(
            f'La mission « {mission.title} » créée par '
            f'{mission.client.username or mission.client.phone_number} '
            f'reste sans agent assigné.'
        ),
        mission=mission,
        metadata={
            'mission_id': str(mission.id),
            'client_id': str(mission.client_id),
            'created_at': mission.created_at.isoformat(),
            'checked_at': timezone.now().isoformat(),
        },
    )
    logger.info('AdminNotification créée pour mission PENDING %s', mission_id)


@shared_task
def cleanup_expired_missions():
    """Nettoyage périodique des missions expirées (placeholder Celery beat)."""
    from apps.missions.models import Mission
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=30)
    stale = Mission.objects.filter(
        status=MissionStatus.PENDING,
        agent__isnull=True,
        created_at__lt=cutoff,
    )
    count = stale.count()
    logger.info('cleanup_expired_missions: %s missions PENDING obsolètes', count)
    return count
