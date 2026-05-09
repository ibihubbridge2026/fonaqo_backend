import uuid
import re
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.core.choices import MissionStatus

class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Mission est optionnelle pour permettre la discussion de prospection
    mission = models.ForeignKey(
        'missions.Mission', 
        on_delete=models.CASCADE, 
        related_name='messages',
        null=True,
        blank=True
    )
    
    # Pour le chat direct (avant mission), on définit l'expéditeur et le destinataire
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='received_messages',
        null=True,
        blank=True
    )
    
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']
        verbose_name = _('message')
        verbose_name_plural = _('messages')

    def __str__(self):
        return f"{self.sender.phone_number}: {self.content[:20]}"

    def save(self, *args, **kwargs):
        # Logique Anti-Fraude : Masquage automatique des numéros de téléphone 
        # tant que la mission n'est pas acceptée/payée.
        if not self.mission or self.mission.status == MissionStatus.PENDING:
            # Remplace les suites de 8 chiffres (format Bénin) par des astérisques
            self.content = re.sub(r'\d{8,}', '********', self.content)
        super().save(*args, **kwargs)