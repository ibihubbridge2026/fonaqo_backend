from django.db import models
from django.conf import settings

class MissionProof(models.Model):
    """
    Preuves photo multiples pour une mission
    Permet à l'agent de télécharger plusieurs photos comme preuve
    """
    mission = models.ForeignKey(
        'missions.Mission',
        on_delete=models.CASCADE,
        related_name='proofs'
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_proofs'
    )

    image = models.ImageField(
        upload_to='missions/proofs/%Y/%m/%d/',
        verbose_name="Photo preuve"
    )

    caption = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Légende"
    )

    is_primary = models.BooleanField(
        default=False,
        help_text="Photo principale affichée en premier"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    location_lat = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Latitude"
    )
    location_lng = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Longitude"
    )

    class Meta:
        verbose_name = "Preuve Photo"
        verbose_name_plural = "Preuves Photos"
        ordering = ['-is_primary', '-created_at']

    def __str__(self):
        return f"Preuve pour mission {self.mission.id} - {self.created_at}"


class MissionTimelineEvent(models.Model):
    """
    Événements détaillés dans la timeline d'une mission
    Pour tracking précis avec timestamps
    """
    EVENT_TYPE_CHOICES = [
        ('created', 'Mission créée'),
        ('published', 'Mission publiée'),
        ('accepted', 'Mission acceptée'),
        ('agent_en_route', 'Agent en route'),
        ('agent_arrived', 'Agent arrivé sur place'),
        ('waiting', 'En attente'),
        ('in_progress', 'En cours de réalisation'),
        ('proofs_uploaded', 'Preuves téléchargées'),
        ('completed', 'Mission terminée'),
        ('validated', 'Mission validée par le client'),
        ('cancelled', 'Mission annulée'),
        ('disputed', 'Litige ouvert'),
    ]

    mission = models.ForeignKey(
        'missions.Mission',
        on_delete=models.CASCADE,
        related_name='timeline_events'
    )

    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES
    )

    occurred_at = models.DateTimeField(auto_now_add=True)

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mission_timeline_events'
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notes additionnelles"
    )

    location_lat = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Latitude"
    )
    location_lng = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Longitude"
    )

    metadata = models.JSONField(
        blank=True,
        null=True,
        help_text="Données supplémentaires au format JSON"
    )

    class Meta:
        verbose_name = "Événement Timeline"
        verbose_name_plural = "Événements Timeline"
        ordering = ['occurred_at']
        indexes = [
            models.Index(fields=['mission', '-occurred_at']),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} - Mission {self.mission.id}"
