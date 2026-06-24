from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _


class PlatformConfiguration(models.Model):
    """Configuration dynamique plateforme (frais, seuils, feature flags)."""

    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('configuration plateforme')
        verbose_name_plural = _('configurations plateforme')
        ordering = ['key']

    def __str__(self):
        return f'{self.key}={self.value}'

    @classmethod
    def get_decimal(cls, key: str, default: Decimal | str = '0') -> Decimal:
        from .services import PlatformConfigService
        return PlatformConfigService.get_decimal(key, default)

    @classmethod
    def get_int(cls, key: str, default: int = 0) -> int:
        from .services import PlatformConfigService
        return PlatformConfigService.get_int(key, default)


class AdminNotification(models.Model):
    """Alertes opérationnelles pour le futur panel SuperAdmin."""

    class Category(models.TextChoices):
        MISSION_UNASSIGNED = 'MISSION_UNASSIGNED', _('Mission non acceptée')
        DISPUTE = 'DISPUTE', _('Litige')
        SECURITY = 'SECURITY', _('Sécurité')
        SYSTEM = 'SYSTEM', _('Système')

    class Severity(models.TextChoices):
        INFO = 'info', _('Info')
        WARNING = 'warning', _('Avertissement')
        CRITICAL = 'critical', _('Critique')

    category = models.CharField(max_length=30, choices=Category.choices)
    severity = models.CharField(
        max_length=10,
        choices=Severity.choices,
        default=Severity.WARNING,
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    mission = models.ForeignKey(
        'missions.Mission',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='admin_notifications',
    )
    is_read = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('notification admin')
        verbose_name_plural = _('notifications admin')
        indexes = [
            models.Index(fields=['is_read', '-created_at']),
            models.Index(fields=['category', '-created_at']),
        ]

    def __str__(self):
        return f'[{self.category}] {self.title}'


class StaffConciergeNote(models.Model):
    """Notes internes staff — mémos conciergerie / support."""

    author = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='concierge_notes',
    )
    content = models.TextField()
    admin_notification = models.ForeignKey(
        AdminNotification,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='concierge_notes',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = _('note conciergerie')
        verbose_name_plural = _('notes conciergerie')

    def __str__(self):
        return f'Note {self.id} — {self.content[:40]}'


class AdminAuditLog(models.Model):
    """Journal des actions SuperAdmin (panel web + API staff)."""

    admin = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='admin_audit_logs',
    )
    action = models.CharField(max_length=80, db_index=True)
    target_type = models.CharField(max_length=50, blank=True, default='')
    target_id = models.CharField(max_length=64, blank=True, default='')
    detail = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('journal audit admin')
        verbose_name_plural = _('journaux audit admin')
        indexes = [
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['target_type', '-created_at']),
        ]

    def __str__(self):
        who = self.admin.username if self.admin_id else 'system'
        return f'{who} — {self.action} @ {self.created_at:%Y-%m-%d %H:%M}'


class SupportFaqEntry(models.Model):
    """FAQ dynamique — affichée dans l'app mobile selon le rôle."""

    class Audience(models.TextChoices):
        CLIENT = 'client', _('Client')
        AGENT = 'agent', _('Agent')
        ALL = 'all', _('Tous')

    audience = models.CharField(max_length=10, choices=Audience.choices, default=Audience.ALL)
    question = models.CharField(max_length=300)
    answer = models.TextField()
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = _('entrée FAQ support')
        verbose_name_plural = _('entrées FAQ support')

    def __str__(self):
        return self.question[:60]


class PasswordResetRequest(models.Model):
    """Demande de réinitialisation mot de passe (parcours SIM manuelle)."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('En attente')
        COMPLETED = 'COMPLETED', _('Traité')
        REJECTED = 'REJECTED', _('Rejeté')

    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='password_reset_requests',
    )
    phone_number = models.CharField(max_length=20, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    temp_password = models.CharField(max_length=128, blank=True, default='')
    processed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_password_resets',
    )
    admin_note = models.TextField(blank=True, default='')
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-requested_at']
        verbose_name = _('demande réinitialisation mot de passe')
        verbose_name_plural = _('demandes réinitialisation mot de passe')

    def __str__(self):
        return f'{self.phone_number} — {self.status}'
