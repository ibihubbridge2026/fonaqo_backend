"""API staff — consultation ledger audit."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.finance.ledger_service import LedgerService
from apps.finance.models import LedgerEntry, LedgerReconciliationRun
from apps.wallets.models import Wallet

_STAFF_AUTH = [SessionAuthentication, JWTAuthentication]

_MAX_PAGE_SIZE = 200
_MAX_EXPORT_ROWS = 10_000


def _parse_date(value: str | None, *, end_of_day: bool = False):
    if not value:
        return None
    try:
        dt = datetime.strptime(value.strip(), '%Y-%m-%d')
    except ValueError:
        return None
    if end_of_day:
        return dt.replace(hour=23, minute=59, second=59)
    return dt


def _ledger_queryset(request):
    qs = LedgerEntry.objects.all().order_by('-occurred_at')

    entry_type = request.query_params.get('entry_type', '').strip()
    if entry_type:
        qs = qs.filter(entry_type=entry_type)

    user_id = request.query_params.get('user_id', '').strip()
    if user_id:
        try:
            qs = qs.filter(user_id=UUID(user_id))
        except ValueError:
            qs = qs.none()

    mission_id = request.query_params.get('mission_id', '').strip()
    if mission_id:
        try:
            qs = qs.filter(mission_id=UUID(mission_id))
        except ValueError:
            qs = qs.none()

    transaction_id = request.query_params.get('transaction_id', '').strip()
    if transaction_id:
        try:
            qs = qs.filter(transaction_id=UUID(transaction_id))
        except ValueError:
            qs = qs.none()

    account = request.query_params.get('account', '').strip()
    if account:
        qs = qs.filter(
            Q(debit_account=account) | Q(credit_account=account),
        )

    search = request.query_params.get('q', '').strip()
    if search:
        qs = qs.filter(
            Q(reference__icontains=search)
            | Q(description__icontains=search)
            | Q(debit_account__icontains=search)
            | Q(credit_account__icontains=search),
        )

    date_from = _parse_date(request.query_params.get('from'))
    if date_from:
        qs = qs.filter(occurred_at__gte=date_from)

    date_to = _parse_date(request.query_params.get('to'), end_of_day=True)
    if date_to:
        qs = qs.filter(occurred_at__lte=date_to)

    return qs


def _serialize_entry(entry: LedgerEntry) -> dict:
    return {
        'id': str(entry.id),
        'entry_type': entry.entry_type,
        'reference': entry.reference,
        'occurred_at': entry.occurred_at.isoformat(),
        'debit_account': entry.debit_account,
        'credit_account': entry.credit_account,
        'amount': str(entry.amount),
        'currency': entry.currency,
        'transaction_id': str(entry.transaction_id) if entry.transaction_id else None,
        'user_id': str(entry.user_id) if entry.user_id else None,
        'mission_id': str(entry.mission_id) if entry.mission_id else None,
        'description': entry.description,
        'metadata': entry.metadata,
        'created_by': entry.created_by,
    }


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def ledger_entries_list(request):
    """Liste paginée des entrées ledger avec filtres."""
    page = max(int(request.query_params.get('page', 1)), 1)
    page_size = min(
        max(int(request.query_params.get('page_size', 50)), 1),
        _MAX_PAGE_SIZE,
    )

    qs = _ledger_queryset(request)
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)

    return Response({
        'count': paginator.count,
        'page': page_obj.number,
        'page_size': page_size,
        'total_pages': paginator.num_pages,
        'results': [_serialize_entry(e) for e in page_obj.object_list],
    })


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def ledger_entry_detail(request, entry_id):
    """Détail d'une entrée ledger."""
    entry = get_object_or_404(LedgerEntry, pk=entry_id)
    return Response(_serialize_entry(entry))


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def ledger_reconciliation_runs(request):
    """Historique des rapprochements nocturnes."""
    limit = min(int(request.query_params.get('limit', 30)), 100)
    runs = LedgerReconciliationRun.objects.order_by('-run_at')[:limit]
    return Response({
        'results': [
            {
                'id': str(r.id),
                'run_at': r.run_at.isoformat(),
                'status': r.status,
                'wallets_checked': r.wallets_checked,
                'mismatches_count': r.mismatches_count,
                'mismatch_details': r.mismatch_details,
                'duration_ms': r.duration_ms,
                'error_message': r.error_message,
            }
            for r in runs
        ],
        'count': len(runs),
    })


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def ledger_user_balance(request, user_id):
    """Comparaison côte à côte Wallet vs Ledger pour un utilisateur."""
    wallet = get_object_or_404(Wallet, user_id=user_id)
    uid = wallet.user_id

    ledger_balance = LedgerService.get_balance(f'wallet:{uid}')
    ledger_escrow = LedgerService.get_balance(f'escrow:{uid}')

    return Response({
        'user_id': str(uid),
        'wallet': {
            'balance': str(wallet.balance),
            'escrow_balance': str(wallet.escrow_balance),
        },
        'ledger': {
            'balance': str(ledger_balance),
            'escrow_balance': str(ledger_escrow),
        },
        'delta': {
            'balance': str(Decimal(wallet.balance) - ledger_balance),
            'escrow_balance': str(Decimal(wallet.escrow_balance) - ledger_escrow),
        },
        'is_reconciled': (
            ledger_balance == Decimal(wallet.balance)
            and ledger_escrow == Decimal(wallet.escrow_balance)
        ),
    })


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def ledger_export_csv(request):
    """Export CSV des entrées ledger (mêmes filtres que la liste)."""
    qs = _ledger_queryset(request)[:_MAX_EXPORT_ROWS]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        'id', 'occurred_at', 'entry_type', 'reference',
        'debit_account', 'credit_account', 'amount', 'currency',
        'user_id', 'mission_id', 'transaction_id', 'description',
    ])

    for entry in qs.iterator():
        writer.writerow([
            entry.id,
            entry.occurred_at.isoformat(),
            entry.entry_type,
            entry.reference,
            entry.debit_account,
            entry.credit_account,
            entry.amount,
            entry.currency,
            entry.user_id or '',
            entry.mission_id or '',
            entry.transaction_id or '',
            entry.description,
        ])

    response = HttpResponse(buffer.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="ledger_export.csv"'
    return response
