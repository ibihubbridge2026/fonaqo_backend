import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class InAppNotification(models.Model):
    """Notification persistée pour l'historique in-app."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default='')
    action = models.CharField(
        max_length=32,
        blank=True,
        default='',
        help_text="Type de navigation: mission, chat, wallet, generic",
    )
    target_id = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text="ID cible (mission, conversation, etc.)",
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")

    def __str__(self):
        return f"{self.title} → {self.user}"
