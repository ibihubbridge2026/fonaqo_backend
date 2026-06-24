"""Alertes opérationnelles staff : stockage + email + logs."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

from apps.core.models import AdminNotification

logger = logging.getLogger(__name__)


def _staff_recipient_emails() -> list[str]:
    override = getattr(settings, 'ADMIN_ALERT_EMAILS', None) or []
    if override:
        return [e.strip() for e in override if e and e.strip()]

    from django.contrib.auth import get_user_model

    User = get_user_model()
    return list(
        User.objects.filter(is_staff=True, is_active=True)
        .exclude(email='')
        .values_list('email', flat=True)
        .distinct(),
    )


def notify_staff(
    *,
    category: str,
    severity: str,
    title: str,
    message: str,
    metadata: dict | None = None,
    send_email: bool = True,
    mission=None,
) -> AdminNotification:
    """
    Crée une AdminNotification et tente l'envoi email aux staff.
    Retourne l'objet persisté (visible via GET /api/v1/staff/notifications/).
    """
    notification = AdminNotification.objects.create(
        category=category,
        severity=severity,
        title=title,
        message=message,
        metadata=metadata or {},
        mission=mission,
    )

    log_fn = logger.info
    if severity == AdminNotification.Severity.CRITICAL:
        log_fn = logger.critical
    elif severity == AdminNotification.Severity.WARNING:
        log_fn = logger.warning

    log_fn('[AdminAlert] %s — %s', title, message)

    if send_email:
        recipients = _staff_recipient_emails()
        if recipients:
            try:
                send_mail(
                    subject=f'[FONAQO {severity.upper()}] {title}',
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=recipients,
                    fail_silently=False,
                )
                notification.metadata = {
                    **notification.metadata,
                    'email_sent_to': recipients,
                }
                notification.save(update_fields=['metadata'])
            except Exception:
                logger.exception(
                    'Échec envoi email alerte staff: %s',
                    title,
                )
                notification.metadata = {
                    **notification.metadata,
                    'email_sent': False,
                }
                notification.save(update_fields=['metadata'])
        else:
            logger.warning(
                'Aucun email staff configuré pour alerte: %s',
                title,
            )

    return notification
