from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Dispute(models.Model):
  """Litige ouvert sur une mission."""

  class Status(models.TextChoices):
    OPEN = 'open', _('Ouvert')
    UNDER_REVIEW = 'under_review', _("En cours d'examen")
    RESOLVED = 'resolved', _('Résolu')
    CLOSED = 'closed', _('Fermé')
    ESCALATED = 'escalated', _('Escaladé')

  class Priority(models.TextChoices):
    LOW = 'low', _('Basse')
    MEDIUM = 'medium', _('Moyenne')
    HIGH = 'high', _('Haute')
    CRITICAL = 'critical', _('Critique')

  title = models.CharField(max_length=200, verbose_name=_('Titre du litige'))
  description = models.TextField(verbose_name=_('Description détaillée'))
  evidence_file = models.FileField(
    upload_to='disputes/evidence/%Y/%m/%d/',
    null=True,
    blank=True,
    verbose_name=_('Preuve (image / document)'),
  )
  status = models.CharField(
    max_length=20,
    choices=Status.choices,
    default=Status.OPEN,
  )
  priority = models.CharField(
    max_length=10,
    choices=Priority.choices,
    default=Priority.MEDIUM,
  )
  resolution_notes = models.TextField(
    blank=True,
    null=True,
    verbose_name=_('Notes de résolution'),
  )
  resolved_at = models.DateTimeField(null=True, blank=True)
  refund_amount = models.DecimalField(
    max_digits=10,
    decimal_places=2,
    null=True,
    blank=True,
    verbose_name=_('Montant remboursé (FCFA)'),
  )
  penalty_amount = models.DecimalField(
    max_digits=10,
    decimal_places=2,
    null=True,
    blank=True,
    verbose_name=_('Pénalité appliquée (FCFA)'),
  )
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)
  mission = models.ForeignKey(
    'missions.Mission',
    on_delete=models.CASCADE,
    related_name='disputes',
  )
  opened_by = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.SET_NULL,
    null=True,
    related_name='opened_disputes',
  )
  assigned_to = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    limit_choices_to={'is_staff': True},
    related_name='assigned_disputes',
  )
  resolved_by = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='resolved_disputes',
  )

  class Meta:
    ordering = ['-created_at']
    verbose_name = _('Litige')
    verbose_name_plural = _('Litiges')
    indexes = [
      models.Index(fields=['status', '-created_at']),
      models.Index(fields=['mission', '-created_at']),
    ]

  def __str__(self):
    return f'Litige {self.pk} — {self.title}'


class DisputeEvidence(models.Model):
  dispute = models.ForeignKey(
    Dispute,
    on_delete=models.CASCADE,
    related_name='evidences',
  )
  uploaded_by = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.SET_NULL,
    null=True,
  )
  file = models.FileField(
    upload_to='disputes/evidences/%Y/%m/%d/',
    verbose_name=_('Fichier preuve'),
  )
  description = models.TextField(blank=True, verbose_name=_('Description de la preuve'))
  created_at = models.DateTimeField(auto_now_add=True)

  class Meta:
    verbose_name = _('Preuve')
    verbose_name_plural = _('Preuves')


class DisputeComment(models.Model):
  dispute = models.ForeignKey(
    Dispute,
    on_delete=models.CASCADE,
    related_name='comments',
  )
  author = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.SET_NULL,
    null=True,
  )
  comment = models.TextField()
  is_internal = models.BooleanField(
    default=True,
    help_text=_('Si vrai, visible uniquement par le staff'),
  )
  created_at = models.DateTimeField(auto_now_add=True)
  edited_at = models.DateTimeField(null=True, blank=True)

  class Meta:
    ordering = ['created_at']
    verbose_name = _('Commentaire')
    verbose_name_plural = _('Commentaires')
