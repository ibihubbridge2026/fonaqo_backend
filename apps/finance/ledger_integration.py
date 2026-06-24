"""
Pont entre les flux Wallet/Escrow et le ledger immuable.
Chaque écriture wallet.Transaction est reflétée en double-entrée LedgerEntry.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from apps.finance.ledger_service import LedgerService
from apps.finance.models import LedgerEntryType

logger = logging.getLogger(__name__)


def _wallet(user_id) -> str:
    return f'wallet:{user_id}'


def _escrow(user_id) -> str:
    return f'escrow:{user_id}'


def _ledger_ref(prefix: str, suffix: str) -> str:
    return f'LEDGER-{prefix}-{suffix}'


def _safe_record(**kwargs) -> None:
    """Enregistre une écriture ledger — ne lève pas si référence déjà existante (idempotent)."""
    try:
        LedgerService.record_entry(**kwargs)
    except ValueError as exc:
        if 'existe déjà' in str(exc):
            logger.info('Ledger entry déjà enregistrée: %s', kwargs.get('reference'))
            return
        raise


def record_feexpay_deposit(
    *,
    user_id: UUID,
    amount: Decimal,
    payment_id: UUID,
    external_reference: str | None,
    wallet_transaction_id: UUID,
) -> None:
    ref = external_reference or str(payment_id)
    _safe_record(
        entry_type=LedgerEntryType.FEEXPAY_DEPOSIT,
        debit_account=_wallet(user_id),
        credit_account='external:feexpay',
        amount=amount,
        reference=_ledger_ref('FEEXPAY', ref),
        transaction_id=wallet_transaction_id,
        user_id=user_id,
        description=f'Dépôt FeexPay {ref}',
        metadata={'payment_id': str(payment_id)},
    )


def record_wallet_deposit(
    *,
    user_id: UUID,
    amount: Decimal,
    wallet_transaction_id: UUID,
    reference: str,
    description: str,
) -> None:
    _safe_record(
        entry_type=LedgerEntryType.WALLET_DEPOSIT,
        debit_account=_wallet(user_id),
        credit_account='external:deposit',
        amount=amount,
        reference=_ledger_ref('DEPOSIT', reference),
        transaction_id=wallet_transaction_id,
        user_id=user_id,
        description=description,
    )


def record_escrow_lock(
    *,
    client_id: UUID,
    mission_id: UUID,
    amount: Decimal,
    wallet_transaction_id: UUID,
) -> None:
    _safe_record(
        entry_type=LedgerEntryType.ESCROW_LOCK,
        debit_account=_escrow(client_id),
        credit_account=_wallet(client_id),
        amount=amount,
        reference=_ledger_ref('ESCROW-LOCK', f'{mission_id}-{wallet_transaction_id}'),
        transaction_id=wallet_transaction_id,
        user_id=client_id,
        mission_id=mission_id,
        description=f'Séquestre mission {mission_id}',
    )


def record_escrow_release_to_agent(
    *,
    agent_id: UUID,
    client_id: UUID,
    mission_id: UUID,
    amount: Decimal,
    wallet_transaction_id: UUID,
) -> None:
    _safe_record(
        entry_type=LedgerEntryType.MISSION_PAYMENT,
        debit_account=_wallet(agent_id),
        credit_account=_escrow(client_id),
        amount=amount,
        reference=_ledger_ref('MISSION-PAY', f'{mission_id}-{wallet_transaction_id}'),
        transaction_id=wallet_transaction_id,
        user_id=agent_id,
        mission_id=mission_id,
        description=f'Paiement agent mission {mission_id}',
    )


def record_platform_revenue(
    *,
    mission_id: UUID,
    amount: Decimal,
    wallet_transaction_id: UUID,
    description: str,
) -> None:
    _safe_record(
        entry_type=LedgerEntryType.ESCROW_RELEASE,
        debit_account='platform:revenue',
        credit_account=f'escrow:mission:{mission_id}',
        amount=amount,
        reference=_ledger_ref('PLATFORM', f'{mission_id}-{wallet_transaction_id}'),
        transaction_id=wallet_transaction_id,
        mission_id=mission_id,
        description=description,
    )


def record_escrow_refund(
    *,
    client_id: UUID,
    mission_id: UUID,
    amount: Decimal,
    wallet_transaction_id: UUID,
    reference: str,
    description: str,
) -> None:
    _safe_record(
        entry_type=LedgerEntryType.ESCROW_REFUND,
        debit_account=_wallet(client_id),
        credit_account=_escrow(client_id),
        amount=amount,
        reference=_ledger_ref('REFUND', reference),
        transaction_id=wallet_transaction_id,
        user_id=client_id,
        mission_id=mission_id,
        description=description,
    )


def record_purchase_transfer_to_agent(
    *,
    agent_id: UUID,
    client_id: UUID,
    mission_id: UUID,
    amount: Decimal,
    wallet_transaction_id: UUID,
) -> None:
    _safe_record(
        entry_type=LedgerEntryType.MISSION_PAYMENT,
        debit_account=_wallet(agent_id),
        credit_account=_wallet(client_id),
        amount=amount,
        reference=_ledger_ref('PURCHASE', f'{mission_id}-{wallet_transaction_id}'),
        transaction_id=wallet_transaction_id,
        user_id=agent_id,
        mission_id=mission_id,
        description=f'Déblocage achats mission {mission_id}',
    )


def record_cancel_compensation(
    *,
    client_id: UUID,
    agent_id: UUID,
    mission_id: UUID,
    client_share: Decimal,
    agent_share: Decimal,
    platform_share: Decimal,
    client_txn_id: UUID,
    agent_txn_id: UUID,
    platform_txn_id: UUID | None = None,
) -> None:
    if client_share > 0:
        _safe_record(
            entry_type=LedgerEntryType.ESCROW_REFUND,
            debit_account=_wallet(client_id),
            credit_account=_escrow(client_id),
            amount=client_share,
            reference=_ledger_ref('CANCEL-CLIENT', f'{mission_id}-{client_txn_id}'),
            transaction_id=client_txn_id,
            user_id=client_id,
            mission_id=mission_id,
            description=f'Remboursement annulation mission {mission_id}',
        )
    if agent_share > 0:
        _safe_record(
            entry_type=LedgerEntryType.MISSION_PAYMENT,
            debit_account=_wallet(agent_id),
            credit_account=_escrow(client_id),
            amount=agent_share,
            reference=_ledger_ref('CANCEL-AGENT', f'{mission_id}-{agent_txn_id}'),
            transaction_id=agent_txn_id,
            user_id=agent_id,
            mission_id=mission_id,
            description=f'Indemnisation annulation mission {mission_id}',
        )
    if platform_share > 0 and platform_txn_id:
        _safe_record(
            entry_type=LedgerEntryType.ESCROW_RELEASE,
            debit_account='platform:revenue',
            credit_account=_escrow(client_id),
            amount=platform_share,
            reference=_ledger_ref('CANCEL-PLATFORM', f'{mission_id}-{platform_txn_id}'),
            transaction_id=platform_txn_id,
            mission_id=mission_id,
            description=f'Frais administratifs annulation mission {mission_id}',
        )


def record_escrow_lock_increase(
    *,
    client_id: UUID,
    mission_id: UUID,
    amount: Decimal,
    wallet_transaction_id: UUID,
) -> None:
    _safe_record(
        entry_type=LedgerEntryType.ESCROW_LOCK,
        debit_account=_escrow(client_id),
        credit_account=_wallet(client_id),
        amount=amount,
        reference=_ledger_ref('ESCROW-AMEND', f'{mission_id}-{wallet_transaction_id}'),
        transaction_id=wallet_transaction_id,
        user_id=client_id,
        mission_id=mission_id,
        description=f'Avenant tarifaire mission {mission_id}',
    )


def record_material_release_to_agent(
    *,
    agent_id: UUID,
    client_id: UUID,
    mission_id: UUID,
    amount: Decimal,
    wallet_transaction_id: UUID,
) -> None:
    _safe_record(
        entry_type=LedgerEntryType.MISSION_PAYMENT,
        debit_account=_wallet(agent_id),
        credit_account=_escrow(client_id),
        amount=amount,
        reference=_ledger_ref('MATERIAL', f'{mission_id}-{wallet_transaction_id}'),
        transaction_id=wallet_transaction_id,
        user_id=agent_id,
        mission_id=mission_id,
        description=f'Déblocage matériel mission {mission_id}',
    )


def record_reserve_revenue(
    *,
    mission_id: UUID,
    amount: Decimal,
    wallet_transaction_id: UUID,
    description: str,
) -> None:
    _safe_record(
        entry_type=LedgerEntryType.ESCROW_RELEASE,
        debit_account='platform:reserve',
        credit_account=f'escrow:mission:{mission_id}',
        amount=amount,
        reference=_ledger_ref('RESERVE', f'{mission_id}-{wallet_transaction_id}'),
        transaction_id=wallet_transaction_id,
        mission_id=mission_id,
        description=description,
    )


def record_payout_approved(
    *,
    user_id: UUID,
    amount: Decimal,
    payout_id: UUID,
    wallet_transaction_id: UUID,
    reference: str,
) -> None:
    _safe_record(
        entry_type=LedgerEntryType.PAYOUT_APPROVED,
        debit_account='external:momo_payout',
        credit_account=_wallet(user_id),
        amount=amount,
        reference=_ledger_ref('PAYOUT', reference),
        transaction_id=wallet_transaction_id,
        user_id=user_id,
        description=f'Retrait approuvé {payout_id}',
        metadata={'payout_id': str(payout_id)},
    )


def record_boost_wallet(
    *,
    user_id: UUID,
    amount: Decimal,
    wallet_transaction_id: UUID,
    reference: str,
) -> None:
    _safe_record(
        entry_type=LedgerEntryType.BOOST_PURCHASE,
        debit_account='platform:revenue',
        credit_account=_wallet(user_id),
        amount=amount,
        reference=_ledger_ref('BOOST-WALLET', reference),
        transaction_id=wallet_transaction_id,
        user_id=user_id,
        description='Achat boost via portefeuille',
    )


def record_boost_feexpay(
    *,
    user_id: UUID,
    amount: Decimal,
    payment_id: UUID,
    wallet_transaction_id: UUID,
    external_reference: str | None,
) -> None:
    ref = external_reference or str(payment_id)
    _safe_record(
        entry_type=LedgerEntryType.BOOST_PURCHASE,
        debit_account='platform:revenue',
        credit_account='external:feexpay',
        amount=amount,
        reference=_ledger_ref('BOOST-FEEX', ref),
        transaction_id=wallet_transaction_id,
        user_id=user_id,
        description=f'Achat boost FeexPay {ref}',
        metadata={'payment_id': str(payment_id)},
    )


def record_influencer_commission(
    *,
    influencer_id: UUID,
    mission_id: UUID,
    amount: Decimal,
) -> None:
    _safe_record(
        entry_type=LedgerEntryType.ESCROW_RELEASE,
        debit_account=f'influencer:{influencer_id}',
        credit_account=f'escrow:mission:{mission_id}',
        amount=amount,
        reference=_ledger_ref('INFLUENCER', f'{mission_id}-{influencer_id}'),
        mission_id=mission_id,
        description=f'Commission influenceur mission {mission_id}',
        metadata={'influencer_id': str(influencer_id)},
    )


def record_manager_commission(
    *,
    manager_id: int,
    mission_id: UUID,
    amount: Decimal,
) -> None:
    """Enregistrement comptable de la commission d'un manager de brigade."""
    _safe_record(
        entry_type=LedgerEntryType.ESCROW_RELEASE,
        debit_account=f'manager:{manager_id}',
        credit_account=f'escrow:mission:{mission_id}',
        amount=amount,
        reference=_ledger_ref('MANAGER', f'{mission_id}-{manager_id}'),
        mission_id=mission_id,
        description=f'Commission manager brigade mission {mission_id}',
        metadata={'manager_id': str(manager_id)},
    )
