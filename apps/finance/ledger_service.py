import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID
from django.db import transaction
from django.utils import timezone

from .models import LedgerEntry, LedgerEntryType

logger = logging.getLogger(__name__)


class LedgerService:
    """Service pour gérer le ledger immuable"""
    
    @staticmethod
    @transaction.atomic
    def record_entry(
        entry_type: str,
        debit_account: str,
        credit_account: str,
        amount: Decimal,
        reference: str,
        transaction_id: UUID = None,
        user_id: UUID = None,
        mission_id: UUID = None,
        description: str = '',
        metadata: dict = None,
        created_by: str = 'system',
    ) -> LedgerEntry:
        """Enregistre une entrée ledger immuable"""
        
        # Vérifier unicité reference
        if LedgerEntry.objects.filter(reference=reference).exists():
            raise ValueError(f"Reference {reference} existe déjà")
        
        # Vérifier équilibre débit/crédit
        if amount <= 0:
            raise ValueError("Amount doit être positif")
        
        # Créer entrée ledger
        entry = LedgerEntry.objects.create(
            entry_type=entry_type,
            reference=reference,
            debit_account=debit_account,
            credit_account=credit_account,
            amount=amount,
            transaction_id=transaction_id,
            user_id=user_id,
            mission_id=mission_id,
            description=description,
            metadata=metadata or {},
            created_by=created_by,
        )
        
        logger.info(
            f"Ledger entry created: {entry_type} | {debit_account} → {credit_account} | {amount}"
        )
        
        return entry
    
    @staticmethod
    def get_balance(account: str, as_of=None) -> Decimal:
        """Calcule le solde d'un compte"""
        from django.db import models
        
        queryset = LedgerEntry.objects.filter(
            models.Q(debit_account=account) | models.Q(credit_account=account)
        )
        
        if as_of:
            queryset = queryset.filter(occurred_at__lte=as_of)
        
        debit_sum = queryset.filter(debit_account=account).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        
        credit_sum = queryset.filter(credit_account=account).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        
        return debit_sum - credit_sum
    
    @staticmethod
    def get_transaction_history(
        user_id: UUID,
        start_date=None,
        end_date=None,
    ):
        """Récupère l'historique transactionnel d'un utilisateur"""
        queryset = LedgerEntry.objects.filter(user_id=user_id)
        
        if start_date:
            queryset = queryset.filter(occurred_at__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(occurred_at__lte=end_date)
        
        return queryset.order_by('-occurred_at')
