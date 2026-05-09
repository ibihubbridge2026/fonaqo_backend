import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Payment(models.Model):
    class PaymentStatus(models.TextChoices):
        PENDING = 'PENDING', _('En attente')
        SUCCESS = 'SUCCESS', _('Réussi')
        FAILED = 'FAILED', _('Échoué')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # FeexPay spécifique
    external_reference = models.CharField(max_length=100, unique=True, null=True, blank=True)
    payment_method = models.CharField(max_length=50, blank=True) # MTN, MOOV, CARD
    
    status = models.CharField(
        max_length=20, 
        choices=PaymentStatus.choices, 
        default=PaymentStatus.PENDING
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payement {self.amount} - {self.status}"