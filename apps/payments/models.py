import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.core.choices import PaymentStatus

class Payment(models.Model):
    class Purpose(models.TextChoices):
        WALLET_DEPOSIT = 'wallet_deposit', _('Recharge portefeuille')
        BOOST_PURCHASE = 'boost_purchase', _('Achat boost')
        MISSION_PAYMENT = 'mission_payment', _('Paiement mission')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=0)

    external_reference = models.CharField(max_length=100, unique=True, null=True, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    purpose = models.CharField(
        max_length=30,
        choices=Purpose.choices,
        default=Purpose.WALLET_DEPOSIT,
    )
    metadata = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payement {self.amount} - {self.status}"