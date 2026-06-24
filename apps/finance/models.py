import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from .exceptions import ImmutableLedgerError


class LedgerEntryQuerySet(models.QuerySet):
    """Empêche les mutations en masse sur le ledger."""

    def update(self, **kwargs):
        raise ImmutableLedgerError(
            'Mise à jour en masse interdite sur LedgerEntry.',
        )

    def delete(self):
        raise ImmutableLedgerError(
            'Suppression en masse interdite sur LedgerEntry.',
        )


class LedgerEntryManager(models.Manager):
    def get_queryset(self):
        return LedgerEntryQuerySet(self.model, using=self._db)


class LedgerEntryType(models.TextChoices):
    """Types d'entrées ledger immuable"""
    
    # Dépôts
    WALLET_DEPOSIT = 'WALLET_DEPOSIT', 'Dépôt wallet'
    FEEXPAY_DEPOSIT = 'FEEXPAY_DEPOSIT', 'Dépôt FeexPay'
    
    # Retraits
    WALLET_WITHDRAWAL = 'WALLET_WITHDRAWAL', 'Retrait wallet'
    PAYOUT_REQUEST = 'PAYOUT_REQUEST', 'Demande retrait'
    PAYOUT_APPROVED = 'PAYOUT_APPROVED', 'Retrait approuvé'
    PAYOUT_REJECTED = 'PAYOUT_REJECTED', 'Retrait rejeté'
    
    # Missions
    ESCROW_LOCK = 'ESCROW_LOCK', 'Blocage séquestre'
    ESCROW_RELEASE = 'ESCROW_RELEASE', 'Libération séquestre'
    ESCROW_REFUND = 'ESCROW_REFUND', 'Remboursement séquestre'
    MISSION_PAYMENT = 'MISSION_PAYMENT', 'Paiement mission'
    
    # Boosts
    BOOST_PURCHASE = 'BOOST_PURCHASE', 'Achat boost'
    BOOST_REFUND = 'BOOST_REFUND', 'Remboursement boost'
    
    # Fidélité
    POINTS_AWARDED = 'POINTS_AWARDED', 'Points attribués'
    POINTS_REDEEMED = 'POINTS_REDEEMED', 'Points échangés'
    
    # Ajustements
    MANUAL_ADJUSTMENT = 'MANUAL_ADJUSTMENT', 'Ajustement manuel'
    CORRECTION = 'CORRECTION', 'Correction erreur'
    REVERSAL = 'REVERSAL', 'Annulation'


class LedgerEntry(models.Model):
    """Entrée ledger immuable — audit trail financier (append-only)."""

    objects = LedgerEntryManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Métadonnées
    entry_type = models.CharField(
        max_length=50,
        choices=LedgerEntryType.choices,
        db_index=True,
    )
    reference = models.CharField(max_length=100, unique=True, db_index=True)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Comptes
    debit_account = models.CharField(max_length=100, db_index=True)
    credit_account = models.CharField(max_length=100, db_index=True)
    
    # Montants
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=3, default='XOF')
    
    # Métadonnées transaction
    transaction_id = models.UUIDField(db_index=True, null=True, blank=True)
    user_id = models.UUIDField(db_index=True, null=True, blank=True)
    mission_id = models.UUIDField(db_index=True, null=True, blank=True)
    
    # Description
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    
    # Audit
    created_by = models.CharField(max_length=100, default='system')
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        db_table = 'ledger'
        indexes = [
            models.Index(fields=['reference']),
            models.Index(fields=['occurred_at']),
            models.Index(fields=['entry_type']),
            models.Index(fields=['debit_account']),
            models.Index(fields=['credit_account']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['user_id']),
            models.Index(fields=['mission_id']),
        ]
        ordering = ['-occurred_at']
    
    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ImmutableLedgerError(
                'LedgerEntry est append-only : modification interdite.',
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableLedgerError(
            'LedgerEntry est append-only : suppression interdite.',
        )

    def __str__(self):
        return f"{self.entry_type} | {self.debit_account} → {self.credit_account} | {self.amount}"


class LedgerReconciliationRun(models.Model):
    """Résultat d'un rapprochement nocturne Ledger ↔ Wallet."""

    class Status(models.TextChoices):
        OK = 'OK', 'OK'
        MISMATCH = 'MISMATCH', 'Écart détecté'
        ERROR = 'ERROR', 'Erreur'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run_at = models.DateTimeField(auto_now_add=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        db_index=True,
    )
    wallets_checked = models.PositiveIntegerField(default=0)
    mismatches_count = models.PositiveIntegerField(default=0)
    mismatch_details = models.JSONField(default=list, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'ledger_reconciliation_runs'
        ordering = ['-run_at']
        indexes = [
            models.Index(fields=['-run_at']),
            models.Index(fields=['status', '-run_at']),
        ]

    def __str__(self):
        return f'Reconciliation {self.run_at:%Y-%m-%d %H:%M} — {self.status}'
