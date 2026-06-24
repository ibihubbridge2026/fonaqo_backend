import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.core.choices import EscrowStatus


class Escrow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mission = models.OneToOneField(
        'missions.Mission',
        on_delete=models.CASCADE,
        related_name='escrow'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=EscrowStatus.choices,
        default=EscrowStatus.HELD,
    )

    def lock_for_dispute(self):
        self.status = EscrowStatus.DISPUTED
        self.save()

    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Séquestre")
        verbose_name_plural = _("Séquestres")

    def __str__(self):
        return f"Escrow {self.mission.id} - {self.status}"


class EscrowSplitRecord(models.Model):
    """Traçabilité des répartitions financières à la libération du séquestre."""

    class BeneficiaryType(models.TextChoices):
        AGENT = 'AGENT', _('Agent')
        CLIENT = 'CLIENT', _('Client')
        PLATFORM = 'PLATFORM', _('Plateforme FONACO')
        INFLUENCER = 'INFLUENCER', _('Influenceur')
        MANAGER = 'MANAGER', _('Manager de Brigade')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mission = models.ForeignKey(
        'missions.Mission',
        on_delete=models.CASCADE,
        related_name='escrow_split_records',
    )
    beneficiary_type = models.CharField(
        max_length=20,
        choices=BeneficiaryType.choices,
    )
    amount_fcfa = models.DecimalField(max_digits=12, decimal_places=2)
    beneficiary_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escrow_split_records',
    )
    influencer = models.ForeignKey(
        'accounts.Influencer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escrow_split_records',
    )
    team_manager = models.ForeignKey(
        'accounts.TeamManager',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escrow_split_records',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('écriture split escrow')
        verbose_name_plural = _('écritures split escrow')
        indexes = [
            models.Index(fields=['mission', '-created_at']),
            models.Index(fields=['beneficiary_type', '-created_at']),
        ]

    def __str__(self):
        return (
            f'Split {self.beneficiary_type} '
            f'{self.amount_fcfa} FCFA — mission {self.mission_id}'
        )
