from datetime import timedelta
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from apps.core.choices import TransactionStatus

from .models import Wallet, Transaction
from .serializers import WalletSerializer, TransactionSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_balance_view(request):
    """Retourne le solde du portefeuille de l'utilisateur connecté."""
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    serializer = WalletSerializer(wallet)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_transactions_view(request):
    """Retourne l'historique des transactions (paginé, 20 par page)."""
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    transaction_type = request.query_params.get('type')
    qs = Transaction.objects.filter(wallet=wallet)
    if transaction_type:
        qs = qs.filter(transaction_type=transaction_type)
    paginator = PageNumberPagination()
    paginator.page_size = int(request.query_params.get('page_size', 20))
    page = paginator.paginate_queryset(qs, request)
    serializer = TransactionSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def wallet_deposit_view(request):
    """Recharge le portefeuille (simulation opérateur mobile / virement test)."""
    amount = request.data.get('amount')
    payment_method = request.data.get('payment_method', 'mobile_money')
    payment_reference = request.data.get('payment_reference', '')

    if amount is None:
        return Response({'error': 'Le montant est requis'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        amount = Decimal(str(amount))
    except (ValueError, TypeError):
        return Response({'error': 'Montant invalide'}, status=status.HTTP_400_BAD_REQUEST)

    if amount <= 0:
        return Response({'error': 'Le montant doit être positif'}, status=status.HTTP_400_BAD_REQUEST)

    wallet, _ = Wallet.objects.get_or_create(user=request.user)

    with db_transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
        wallet.balance += amount
        wallet.save(update_fields=['balance', 'updated_at'])
        txn = Transaction.objects.create(
            wallet=wallet,
            amount=amount,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            description=f'Recharge {payment_method}: {payment_reference}'.strip(': '),
        )

    return Response(
        {
            'status': 'success',
            'message': f'Recharge de {amount} FCFA effectuée',
            'transaction_id': str(txn.id),
            'new_balance': float(wallet.balance),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def wallet_withdraw_view(request):
    """Demande de retrait depuis le wallet (débit immédiat, statut PENDING)."""
    if request.user.is_client and not request.user.is_agent:
        raise PermissionDenied(
            "Les comptes clients ne sont pas autorisés à effectuer des retraits."
        )

    raw_amount = request.data.get('amount')
    payment_method = (request.data.get('payment_method') or '').strip()
    phone_number = (request.data.get('phone_number') or '').strip()
    if not phone_number:
        phone_number = (request.data.get('payment_details') or '').strip()

    if raw_amount is None or raw_amount == '':
        return Response(
            {'message': 'Le montant est requis'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        amount = Decimal(str(raw_amount))
    except (ValueError, TypeError, ArithmeticError):
        return Response(
            {'message': 'Montant invalide'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if amount <= 0:
        return Response(
            {'message': 'Le montant doit être positif'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not payment_method:
        return Response(
            {'message': "L'opérateur Mobile Money est requis"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not phone_number:
        return Response(
            {'message': 'Le numéro de téléphone est requis'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    txn = None

    with db_transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

        ten_seconds_ago = timezone.now() - timedelta(seconds=10)
        duplicate_pending = Transaction.objects.filter(
            wallet=wallet,
            transaction_type=Transaction.TransactionType.WITHDRAWAL,
            status=TransactionStatus.PENDING,
            amount=amount,
            created_at__gte=ten_seconds_ago,
        ).exists()
        if duplicate_pending:
            return Response(
                {
                    'message': (
                        'Une demande de retrait identique est déjà en cours '
                        'de traitement. Veuillez patienter.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if wallet.balance < amount:
            return Response(
                {
                    'message': (
                        'Solde insuffisant pour effectuer cette demande de retrait.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        wallet.balance -= amount
        wallet.save(update_fields=['balance', 'updated_at'])
        txn = Transaction.objects.create(
            wallet=wallet,
            amount=amount,
            transaction_type=Transaction.TransactionType.WITHDRAWAL,
            status=TransactionStatus.PENDING,
            description=(
                f'Demande de retrait vers {payment_method} ({phone_number})'
            ),
        )

    return Response(
        {
            'status': 'success',
            'message': 'Demande de retrait enregistrée avec succès',
            'transaction_id': str(txn.id),
            'new_balance': float(wallet.balance),
        },
        status=status.HTTP_201_CREATED,
    )
