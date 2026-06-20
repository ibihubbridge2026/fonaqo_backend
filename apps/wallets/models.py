import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords
from apps.core.choices import PayoutRequestStatus, TransactionStatus

class Wallet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='wallet'
    )
    balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0.00,
        verbose_name=_("Solde disponible")
    )
    escrow_balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0.00,
        verbose_name=_("Solde en séquestre")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()
    
    class Meta:
        verbose_name = _("Portefeuille")
        verbose_name_plural = _("Portefeuilles")

    def __str__(self):
        user_identifier = self.user.phone_number or self.user.email or self.user.username or f"User-{self.user.id}"
        return f"Wallet {user_identifier} ({self.balance} FCFA)"


class Transaction(models.Model):
    # Approche Senior : Utilisation de TextChoices pour la clarté et l'i18n
    class TransactionType(models.TextChoices):
        DEPOSIT = 'DEPOSIT', _('Dépôt')
        WITHDRAWAL = 'WITHDRAWAL', _('Retrait')
        MISSION_PAYMENT = 'MISSION_PAYMENT', _('Paiement de mission')
        ESCROW_LOCK = 'ESCROW_LOCK', _('Blocage Séquestre')
        ESCROW_RELEASE = 'ESCROW_RELEASE', _('Libération Séquestre')
        BOOST_PAYMENT = 'BOOST_PAYMENT', _('Achat de Boost')
        REFERRAL_BONUS = 'REFERRAL_BONUS', _('Bonus Parrainage')
        INSURANCE_FEE = 'INSURANCE_FEE', _('Frais Assurance')
        TRANSFER = 'TRANSFER', _('Transfert')
        BADGE_FEE = 'BADGE_FEE', _('Badge Professionnel')
        
    mission = models.ForeignKey('missions.Mission', on_delete=models.SET_NULL, null=True, blank=True)    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        Wallet, 
        on_delete=models.CASCADE, 
        related_name='transactions'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Montant"))
    transaction_type = models.CharField(
        max_length=20, 
        choices=TransactionType.choices,
        verbose_name=_("Type de transaction")
    )
    status = models.CharField(
        max_length=20,
        choices=TransactionStatus.choices,
        default=TransactionStatus.COMPLETED,
    )
    reference = models.CharField(
        max_length=100, 
        unique=True, 
        null=True, 
        blank=True,
        verbose_name=_("Référence externe")
    )
    description = models.TextField(blank=True, verbose_name=_("Description"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Transaction")
        verbose_name_plural = _("Transactions")

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} FCFA"


class PayoutRequest(models.Model):
    """Demande de retrait agent — workflow staff (approve / reject)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='payout_requests',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_('Montant'))
    payment_method = models.CharField(max_length=50, verbose_name=_('Opérateur MoMo'))
    phone_number = models.CharField(max_length=20, verbose_name=_('Numéro de versement'))
    status = models.CharField(
        max_length=20,
        choices=PayoutRequestStatus.choices,
        default=PayoutRequestStatus.PENDING,
        db_index=True,
    )
    ledger_transaction = models.OneToOneField(
        Transaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payout_request',
        help_text=_('Écriture comptable WITHDRAWAL créée à l\'approbation'),
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_payouts',
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Demande de retrait')
        verbose_name_plural = _('Demandes de retrait')
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f'PayoutRequest {self.amount} FCFA — {self.status}'