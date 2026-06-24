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


STANDARD_MISSION_NOTIFICATION_DELAY_SECONDS = 600

STANDARD_MISSION_NOTIFICATION_BODY = (
    'Une nouvelle mission a été publiée ! Elle est désormais disponible pour vous '
    '(Passez Premium pour y accéder 10 min avant les autres !)'
)


def _agent_has_active_boost(user) -> bool:
    from apps.boosts.models import AgentBoost

    now = timezone.now()
    return AgentBoost.objects.filter(
        agent=user,
        status='active',
        expires_at__gt=now,
    ).exists()


@shared_task
def send_delayed_notification(mission_id: str, agent_ids: list):
    """
    Notifie les agents standard 10 min après publication d'une mission.
    Ignore les agents ayant activé un boost entre-temps.
    """
    from django.contrib.auth import get_user_model

    from apps.accounts.models import AgentProfile
    from apps.core.choices import AgentKYCStatus, MissionStatus
    from apps.missions.models import Mission
    from apps.notifications.services import NotificationService

    User = get_user_model()

    try:
        mission = Mission.objects.get(pk=mission_id)
    except Mission.DoesNotExist:
        logger.warning('send_delayed_notification: mission %s introuvable', mission_id)
        return

    if mission.agent_id is not None:
        logger.info(
            'send_delayed_notification: mission %s déjà assignée, notifications ignorées',
            mission_id,
        )
        return

    if mission.status != MissionStatus.PENDING:
        logger.info(
            'send_delayed_notification: mission %s statut=%s, notifications ignorées',
            mission_id,
            mission.status,
        )
        return

    title = 'Nouvelle mission disponible'
    body = STANDARD_MISSION_NOTIFICATION_BODY
    data = {
        'type': 'NEW_MISSION',
        'mission_id': str(mission.id),
        'delay_minutes': '0',
        'tier': 'standard',
    }

    if not agent_ids:
        return

    agents = User.objects.filter(
        pk__in=agent_ids,
        is_agent=True,
        is_active=True,
    )
    sent = 0
    for agent in agents:
        profile = AgentProfile.objects.filter(user=agent).first()
        if not profile or profile.kyc_status != AgentKYCStatus.APPROVED:
            continue
        if _agent_has_active_boost(agent):
            continue
        NotificationService.send_to_user(agent, title, body, data=data)
        NotificationService.create_in_app_notification(agent, title, body, data=data)
        sent += 1

    logger.info(
        'send_delayed_notification: mission=%s notifications standard envoyées=%s',
        mission_id,
        sent,
    )


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
