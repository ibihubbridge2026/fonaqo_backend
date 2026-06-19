import logging

from django.core.mail import send_mail
from django.conf import settings

from apps.notifications.services import NotificationService

logger = logging.getLogger(__name__)


def notify_dispute_resolution(dispute):
    """Notifie client et agent quand un litige est résolu (push + in-app + e-mail)."""
    mission = dispute.mission
    participants = {mission.client, mission.agent}
    participants.discard(None)

    title = 'Litige résolu'
    body = (
        f'Le litige « {dispute.title} » concernant la mission '
        f'« {mission.title[:80]} » a été traité par l\'administration.'
    )
    if dispute.resolution_notes:
        body += f' Réponse : {dispute.resolution_notes[:200]}'

    data = {
        'type': 'DISPUTE_RESOLVED',
        'mission_id': str(mission.id),
        'dispute_id': str(dispute.id),
    }

    for user in participants:
        NotificationService.send_to_user(user, title, body, data=data)
        NotificationService.create_in_app_notification(user, title, body, data=data)
        _send_dispute_resolution_email(user, dispute)


def _send_dispute_resolution_email(user, dispute):
    if not user.email:
        return
    mission = dispute.mission
    subject = f'[FONACO] Résolution du litige — {dispute.title}'
    message = (
        f'Bonjour,\n\n'
        f'Votre litige concernant la mission « {mission.title} » '
        f'a été traité.\n\n'
        f'Statut : {dispute.get_status_display()}\n'
    )
    if dispute.resolution_notes:
        message += f'Réponse administration :\n{dispute.resolution_notes}\n\n'
    if dispute.refund_amount:
        message += f'Montant remboursé : {dispute.refund_amount} FCFA\n'
    if dispute.penalty_amount:
        message += f'Pénalité appliquée : {dispute.penalty_amount} FCFA\n'
    message += '\n— Équipe FONACO'

    try:
        send_mail(
            subject,
            message,
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@fonaqo.com'),
            [user.email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.error('Échec envoi e-mail litige %s: %s', dispute.id, exc)
