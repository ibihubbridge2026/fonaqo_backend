from django.db import models
from django.conf import settings
from django.utils import timezone

class Dispute(models.Model):
    """
    Litige ouvert par un client ou un agent sur une mission
    """
    STATUS_CHOICES = [
        ('open', 'Ouvert'),
        ('under_review', 'En cours d\'examen'),
        ('resolved', 'Résolu'),
        ('closed', 'Fermé'),
        ('escalated', 'Escaladé'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Basse'),
        ('medium', 'Moyenne'),
        ('high', 'Haute'),
        ('critical', 'Critique'),
    ]

    # Mission concernée
    mission = models.ForeignKey(
        'missions.Mission',
        on_delete=models.CASCADE,
        related_name='disputes'
    )

    # Ouvert par
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='opened_disputes'
    )

    # Assigné à (support/admin)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_disputes',
        limit_choices_to={'is_staff': True}
    )

    # Détails
    title = models.CharField(max_length=200, verbose_name="Titre du litige")
    description = models.TextField(verbose_name="Description détaillée")
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open'
    )
    
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium'
    )

    # Résolution
    resolution_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notes de résolution"
    )
    
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_disputes'
    )

    # Impact financier (remboursement, pénalité, etc.)
    refund_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Montant remboursé (FCFA)"
    )
    
    penalty_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Pénalité appliquée (FCFA)"
    )

    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Litige"
        verbose_name_plural = "Litiges"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['mission', '-created_at']),
        ]

    def __str__(self):
        return f"Litige #{self.id} - {self.title} ({self.status})"

    @property
    def is_open(self):
        return self.status in ['open', 'under_review', 'escalated']

    @property
    def days_open(self):
        """Nombre de jours depuis l'ouverture"""
        delta = timezone.now() - self.created_at
        return delta.days


class DisputeEvidence(models.Model):
    """
    Preuves associées à un litige (photos, documents, captures)
    """
    dispute = models.ForeignKey(
        Dispute,
        on_delete=models.CASCADE,
        related_name='evidences'
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )

    file = models.FileField(
        upload_to='disputes/evidences/%Y/%m/%d/',
        verbose_name="Fichier preuve"
    )

    description = models.TextField(
        blank=True,
        verbose_name="Description de la preuve"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Preuve"
        verbose_name_plural = "Preuves"


class DisputeComment(models.Model):
    """
    Commentaires internes entre support et parties prenantes
    """
    dispute = models.ForeignKey(
        Dispute,
        on_delete=models.CASCADE,
        related_name='comments'
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )

    comment = models.TextField()

    is_internal = models.BooleanField(
        default=True,
        help_text="Si vrai, visible uniquement par le staff"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Commentaire"
        verbose_name_plural = "Commentaires"
        ordering = ['created_at']

    def __str__(self):
        visibility = "Interne" if self.is_internal else "Public"
        return f"Commentaire {visibility} par {self.author.username if self.author else 'Inconnu'}"
