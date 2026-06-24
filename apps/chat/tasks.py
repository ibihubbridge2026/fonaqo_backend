"""Tâches Celery pour le module chat."""

from datetime import timedelta

from celery import shared_task
from django.utils import timezone


@shared_task
def cleanup_expired_typing_statuses():
    """
    Supprimer les TypingStatus expirés (> 10 secondes).
    AUDIT FIX [P2] — Évite l'accumulation d'entrées orphelines.
    """
    from apps.chat.models import TypingStatus

    cutoff = timezone.now() - timedelta(seconds=10)
    deleted_count, _ = TypingStatus.objects.filter(updated_at__lt=cutoff).delete()
    return f"Supprimé {deleted_count} TypingStatus expirés"
