"""Rapprochement nocturne Ledger ↔ Wallet."""

from __future__ import annotations

import logging
import time
from decimal import Decimal

from django.db import transaction

from apps.core.admin_alert_service import notify_staff
from apps.core.models import AdminNotification
from apps.finance.ledger_service import LedgerService
from apps.finance.models import LedgerReconciliationRun
from apps.wallets.models import Wallet

logger = logging.getLogger(__name__)

PLATFORM_USER_EMAIL = 'platform@fonaqo.system'
RESERVE_USER_EMAIL = 'reserve@fonaqo.system'


def _wallet_account(user_id) -> str:
    return f'wallet:{user_id}'


def _escrow_account(user_id) -> str:
    return f'escrow:{user_id}'


def _compare_wallet(wallet: Wallet) -> list[dict]:
    """Compare un wallet opérationnel à ses comptes ledger."""
    mismatches = []
    user_id = wallet.user_id

    ledger_balance = LedgerService.get_balance(_wallet_account(user_id))
    ledger_escrow = LedgerService.get_balance(_escrow_account(user_id))

    op_balance = Decimal(wallet.balance)
    op_escrow = Decimal(wallet.escrow_balance)

    if ledger_balance != op_balance:
        mismatches.append({
            'user_id': str(user_id),
            'account': 'balance',
            'wallet_value': str(op_balance),
            'ledger_value': str(ledger_balance),
            'delta': str(op_balance - ledger_balance),
        })

    if ledger_escrow != op_escrow:
        mismatches.append({
            'user_id': str(user_id),
            'account': 'escrow_balance',
            'wallet_value': str(op_escrow),
            'ledger_value': str(ledger_escrow),
            'delta': str(op_escrow - ledger_escrow),
        })

    return mismatches


def run_reconciliation(*, notify_on_mismatch: bool = True) -> LedgerReconciliationRun:
    """
    Rapproche tous les wallets utilisateur avec leurs comptes ledger.
    Retourne un enregistrement LedgerReconciliationRun persisté.
    """
    started = time.monotonic()
    mismatches: list[dict] = []
    wallets_checked = 0

    try:
        for wallet in Wallet.objects.select_related('user').iterator():
            wallets_checked += 1
            mismatches.extend(_compare_wallet(wallet))

        status = (
            LedgerReconciliationRun.Status.OK
            if not mismatches
            else LedgerReconciliationRun.Status.MISMATCH
        )
        duration_ms = int((time.monotonic() - started) * 1000)

        with transaction.atomic():
            run = LedgerReconciliationRun.objects.create(
                status=status,
                wallets_checked=wallets_checked,
                mismatches_count=len(mismatches),
                mismatch_details=mismatches[:500],
                duration_ms=duration_ms,
            )

            if mismatches and notify_on_mismatch:
                notify_staff(
                    category=AdminNotification.Category.SYSTEM,
                    severity=AdminNotification.Severity.CRITICAL,
                    title='Écart Ledger ↔ Wallet détecté',
                    message=(
                        f'{len(mismatches)} écart(s) sur {wallets_checked} wallet(s).\n'
                        f'Consultez GET /api/v1/staff/ledger/reconciliation/ '
                        f'et GET /api/v1/staff/notifications/.'
                    ),
                    metadata={
                        'run_id': str(run.id),
                        'mismatches_count': len(mismatches),
                        'sample': mismatches[:10],
                    },
                )

        if mismatches:
            logger.critical(
                'Ledger reconciliation MISMATCH: %s écarts sur %s wallets',
                len(mismatches),
                wallets_checked,
            )
        else:
            logger.info(
                'Ledger reconciliation OK: %s wallets vérifiés en %sms',
                wallets_checked,
                duration_ms,
            )

        return run

    except Exception as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.exception('Ledger reconciliation failed')
        return LedgerReconciliationRun.objects.create(
            status=LedgerReconciliationRun.Status.ERROR,
            wallets_checked=wallets_checked,
            mismatches_count=0,
            mismatch_details=[],
            duration_ms=duration_ms,
            error_message=str(exc),
        )
