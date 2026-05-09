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
    
    # Dates de traçabilité
    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Séquestre")
        verbose_name_plural = _("Séquestres")

    def __str__(self):
        return f"Escrow {self.mission.id} - {self.status}"