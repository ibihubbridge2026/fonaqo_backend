"""Modèle de notation bilatéral pour missions."""

import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _


class Rating(models.Model):
    """Notation bilatérale : client note agent, agent note client."""

    class RatingType(models.TextChoices):
        CLIENT_RATES_AGENT = 'CLIENT_RATES_AGENT', _('Client note agent')
        AGENT_RATES_CLIENT = 'AGENT_RATES_CLIENT', _('Agent note client')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mission = models.ForeignKey(
        'missions.Mission',
        on_delete=models.CASCADE,
        related_name='ratings',
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='given_ratings',
    )
    reviewee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_ratings',
    )
    rating_type = models.CharField(
        max_length=30,
        choices=RatingType.choices,
    )
    score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_('Note (1-5)'),
    )
    comment = models.TextField(
        blank=True,
        verbose_name=_('Commentaire'),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Notation')
        verbose_name_plural = _('Notations')
        unique_together = [['mission', 'reviewer', 'rating_type']]
        indexes = [
            models.Index(fields=['mission', 'rating_type']),
            models.Index(fields=['reviewee', '-created_at']),
        ]

    def __str__(self):
        return f'{self.rating_type} — {self.reviewer} → {self.reviewee} ({self.score}/5)'
