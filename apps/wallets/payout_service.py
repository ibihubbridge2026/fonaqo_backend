"""Service métier des demandes de retrait (PayoutRequest)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.choices import PayoutRequestStatus, TransactionStatus
from apps.finance import ledger_integration

from .models import PayoutRequest, Transaction, Wallet


class PayoutServiceError(ValueError):
    """Erreur métier sur une demande de retrait."""


class PayoutService:
    """Workflow retrait : demande → modération staff → écriture comptable."""

    @staticmethod
    def _pending_total(wallet: Wallet) -> Decimal:
        total = wallet.payout_requests.filter(
            status=PayoutRequestStatus.PENDING,
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        return Decimal(total)

    @classmethod
    def available_balance(cls, wallet: Wallet) -> Decimal:
        """Solde disponible après réservation des retraits PENDING."""
        return Decimal(wallet.balance) - cls._pending_total(wallet)

    @classmethod
    @transaction.atomic
    def request_withdrawal(
        cls,
        *,
        wallet: Wallet,
        amount: Decimal,
        payment_method: str,
        phone_number: str,
    ) -> PayoutRequest:
        wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
        amount = Decimal(str(amount))

        if amount <= 0:
            raise PayoutServiceError('Le montant doit être positif.')

        if cls.available_balance(wallet) < amount:
            raise PayoutServiceError(
                'Solde insuffisant (retraits en attente inclus).',
            )

        return PayoutRequest.objects.create(
            wallet=wallet,
            amount=amount,
            payment_method=payment_method,
            phone_number=phone_number,
            status=PayoutRequestStatus.PENDING,
        )

    @classmethod
    @transaction.atomic
    def approve(cls, payout: PayoutRequest, *, admin_user, provider_transaction_id: str = None) -> PayoutRequest:
        payout = PayoutRequest.objects.select_for_update().get(pk=payout.pk)

        if payout.status != PayoutRequestStatus.PENDING:
            raise PayoutServiceError(
                f'Demande déjà traitée (statut {payout.status}).',
            )

        # Idempotency : vérifier si ce provider_transaction_id a déjà été utilisé
        if provider_transaction_id:
            existing = PayoutRequest.objects.filter(
                provider_transaction_id=provider_transaction_id,
                status=PayoutRequestStatus.COMPLETED
            ).first()
            if existing:
                raise PayoutServiceError(
                    f'Ce provider_transaction_id a déjà été utilisé pour la demande {existing.id}.'
                )

        wallet = Wallet.objects.select_for_update().get(pk=payout.wallet_id)

        if wallet.balance < payout.amount:
            raise PayoutServiceError(
                'Solde insuffisant au moment de l\'approbation.',
            )

        wallet.balance -= payout.amount
        wallet.save(update_fields=['balance', 'updated_at'])

        ledger = Transaction.objects.create(
            wallet=wallet,
            amount=payout.amount,
            transaction_type=Transaction.TransactionType.WITHDRAWAL,
            status=TransactionStatus.COMPLETED,
            reference=f'PAYOUT-{uuid.uuid4().hex[:12].upper()}',
            description=(
                f'Retrait approuvé → {payout.payment_method} '
                f'({payout.phone_number})'
            ),
        )

        ledger_integration.record_payout_approved(
            user_id=wallet.user_id,
            amount=payout.amount,
            payout_id=payout.id,
            wallet_transaction_id=ledger.id,
            reference=ledger.reference,
        )

        payout.status = PayoutRequestStatus.COMPLETED
        payout.ledger_transaction = ledger
        payout.processed_by = admin_user
        payout.processed_at = timezone.now()
        if provider_transaction_id:
            payout.provider_transaction_id = provider_transaction_id
        payout.save(update_fields=[
            'status', 'ledger_transaction', 'processed_by',
            'processed_at', 'provider_transaction_id', 'updated_at',
        ])
        return payout

    @classmethod
    @transaction.atomic
    def reject(
        cls,
        payout: PayoutRequest,
        *,
        admin_user,
        reason: str = '',
    ) -> PayoutRequest:
        payout = PayoutRequest.objects.select_for_update().get(pk=payout.pk)

        if payout.status != PayoutRequestStatus.PENDING:
            raise PayoutServiceError(
                f'Demande déjà traitée (statut {payout.status}).',
            )

        payout.status = PayoutRequestStatus.REJECTED
        payout.processed_by = admin_user
        payout.processed_at = timezone.now()
        payout.rejection_reason = reason or ''
        payout.save(update_fields=[
            'status', 'processed_by', 'processed_at',
            'rejection_reason', 'updated_at',
        ])
        return payout
