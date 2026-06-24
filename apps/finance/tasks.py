"""Tâches Celery finance / ledger."""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='apps.finance.tasks.reconcile_wallet_ledger')
def reconcile_wallet_ledger():
    """Rapprochement nocturne Ledger ↔ Wallet."""
    from apps.finance.reconciliation import run_reconciliation

    run = run_reconciliation()
    return {
        'run_id': str(run.id),
        'status': run.status,
        'wallets_checked': run.wallets_checked,
        'mismatches_count': run.mismatches_count,
    }
