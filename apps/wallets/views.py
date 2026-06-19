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
        amount = Decimal(str(amount)).quantize(Decimal('1'))
    except (ValueError, TypeError):
        return Response({'error': 'Montant invalide'}, status=status.HTTP_400_BAD_REQUEST)

    if amount <= 0:
        return Response({'error': 'Le montant doit être positif'}, status=status.HTTP_400_BAD_REQUEST)

    payment_method = (request.data.get('payment_method') or 'mobile_money').lower()
    payment_reference = (request.data.get('payment_reference') or '').strip()

    if payment_method == 'feexpay':
        if not payment_reference:
            return Response(
                {'error': 'Référence FeexPay requise'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from apps.payments.models import Payment
            from apps.payments.services import FeexPayService
            payment = FeexPayService.verify_payment(
                request.user,
                payment_reference,
                expected_amount=amount,
                purpose=Payment.Purpose.WALLET_DEPOSIT,
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        wallet = Wallet.objects.get(user=request.user)
        wallet.refresh_from_db()
        return Response(
            {
                'status': 'success',
                'message': f'Recharge de {amount} FCFA créditée via FeexPay',
                'new_balance': float(wallet.balance),
                'payment_id': str(payment.id),
            },
            status=status.HTTP_200_OK,
        )

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
    """Demande de retrait — crée un PayoutRequest PENDING (débit à l'approbation staff)."""
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

    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    if wallet.balance <= Decimal('2000'):
        return Response(
            {'message': 'Solde insuffisant pour un retrait (minimum 2 001 FCFA)'},
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

    from apps.wallets.payout_service import PayoutService, PayoutServiceError

    wallet, _ = Wallet.objects.get_or_create(user=request.user)

    ten_seconds_ago = timezone.now() - timedelta(seconds=10)
    from apps.wallets.models import PayoutRequest
    from apps.core.choices import PayoutRequestStatus

    duplicate_pending = PayoutRequest.objects.filter(
        wallet=wallet,
        status=PayoutRequestStatus.PENDING,
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

    try:
        payout = PayoutService.request_withdrawal(
            wallet=wallet,
            amount=amount,
            payment_method=payment_method,
            phone_number=phone_number,
        )
    except PayoutServiceError as exc:
        return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    wallet.refresh_from_db()
    return Response(
        {
            'status': 'success',
            'message': 'Demande de retrait enregistrée avec succès',
            'payout_id': str(payout.id),
            'payout_status': payout.status,
            'new_balance': float(wallet.balance),
            'available_balance': float(PayoutService.available_balance(wallet)),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_export_csv_view(request):
    """Export CSV des transactions du portefeuille."""
    import csv
    from django.http import HttpResponse

    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    rows = Transaction.objects.filter(wallet=wallet).order_by('-created_at')[:500]

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="releve_fonaco.csv"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Type', 'Montant', 'Description', 'Statut'])
    for tx in rows:
        writer.writerow([
            tx.created_at.strftime('%Y-%m-%d %H:%M'),
            tx.transaction_type,
            float(tx.amount),
            tx.description,
            tx.status,
        ])
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_export_pdf_view(request):
    """Export PDF simple des transactions."""
    from django.http import HttpResponse
    from io import BytesIO

    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at')[:100]

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        y = 800
        c.setFont('Helvetica-Bold', 14)
        c.drawString(50, y, 'FONACO — Relevé de compte')
        y -= 24
        c.setFont('Helvetica', 10)
        c.drawString(50, y, f'Utilisateur : {request.user.get_full_name() or request.user.username}')
        y -= 16
        c.drawString(50, y, f'Solde actuel : {wallet.balance} FCFA')
        y -= 24
        for tx in transactions:
            if y < 60:
                c.showPage()
                y = 800
            line = (
                f'{tx.created_at:%Y-%m-%d %H:%M} | {tx.transaction_type} | '
                f'{tx.amount} FCFA | {tx.description[:40]}'
            )
            c.drawString(50, y, line)
            y -= 14
        c.save()
        pdf = buffer.getvalue()
    except ImportError:
        pdf = b'%PDF-1.4\nReleve FONACO - reportlab requis\n'

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="releve_fonaco.pdf"'
    return response
