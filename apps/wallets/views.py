from decimal import Decimal

from django.conf import settings
from django.db import transaction as db_transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsAgent
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from apps.core.choices import TransactionStatus, PaymentStatus
from apps.payments.models import Payment
from apps.payments.serializers import WalletDepositSerializer
from apps.payments.services import FeexPayService

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
    """
    Recharge le portefeuille via FeexPay (Mobile Money / Carte) ou simulation sandbox.
    AUDIT FIX [P0+P1] — Idempotency sur reference + validation montants.
    """
    serializer = WalletDepositSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    amount = serializer.validated_data['amount']
    payment_method = (serializer.validated_data.get('payment_method') or 'MOBILE').upper()
    payment_reference = (serializer.validated_data.get('payment_reference') or '').strip()
    phone_number = serializer.validated_data.get('phone_number') or ''
    network = serializer.validated_data.get('network', 'MTN')
    card_type = serializer.validated_data.get('card_type') or 'VISA'

    # Legacy : confirmation d'un paiement FeexPay déjà initié
    if payment_method == 'FEEXPAY':
        if not payment_reference:
            return Response(
                {'error': 'Référence FeexPay requise'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
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
                'reference': payment.external_reference,
            },
            status=status.HTTP_200_OK,
        )

    # FeexPay Mobile Money ou Carte — initiation
    if payment_method in ('MOBILE', 'CARD'):
        if not phone_number:
            return Response(
                {'error': 'Numéro de téléphone requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            payment, result = FeexPayService.initiate_wallet_deposit(
                user=request.user,
                amount=amount,
                phone_number=phone_number,
                network=network,
                payment_method=payment_method,
                card_type=card_type,
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not result.get('success'):
            return Response({'error': result.get('message', 'Erreur FeexPay')}, status=400)

        response_data = {
            'success': True,
            'reference': payment.external_reference,
            'payment_id': str(payment.id),
            'status': result.get('status', 'PENDING'),
            'message': result.get('message', ''),
        }
        if result.get('redirect_url'):
            response_data['redirect_url'] = result['redirect_url']
            return Response(response_data, status=status.HTTP_200_OK)
        return Response(response_data, status=status.HTTP_202_ACCEPTED)

    # Simulation sandbox uniquement (dev/test)
    if payment_method == 'MOBILE_MONEY' and getattr(settings, 'DEBUG', False):
        if payment_reference:
            if Transaction.objects.filter(reference=payment_reference).exists():
                return Response(
                    {'error': 'Référence déjà utilisée'},
                    status=status.HTTP_409_CONFLICT,
                )
        else:
            payment_reference = FeexPayService.generate_reference('SIM')

        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        with db_transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
            wallet.balance += amount
            wallet.save(update_fields=['balance', 'updated_at'])
            txn = Transaction.objects.create(
                wallet=wallet,
                amount=amount,
                transaction_type=Transaction.TransactionType.DEPOSIT,
                reference=payment_reference,
                description=f'Recharge simulation: {payment_reference}',
            )

        return Response(
            {
                'status': 'success',
                'message': f'Recharge de {amount} FCFA effectuée (simulation)',
                'transaction_id': str(txn.id),
                'reference': payment_reference,
                'new_balance': float(wallet.balance),
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(
        {'error': 'Méthode de paiement invalide (MOBILE, CARD ou feexpay)'},
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def feexpay_payment_status_view(request, reference):
    """
    Vérifier le statut d'un paiement FeexPay par référence (polling Flutter).
    """
    try:
        payment = Payment.objects.get(
            external_reference=reference,
            user=request.user,
        )
    except Payment.DoesNotExist:
        return Response({'error': 'Transaction introuvable'}, status=404)

    payment = FeexPayService.refresh_payment_status(payment)

    return Response({
        'reference': payment.external_reference,
        'status': payment.status,
        'amount': str(payment.amount),
        'payment_method': payment.payment_method,
        'created_at': payment.created_at.isoformat(),
        'is_credited': payment.status == PaymentStatus.SUCCESS,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAgent])
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

    max_rows = getattr(settings, 'MAX_EXPORT_ROWS', 1000)
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    rows = Transaction.objects.filter(wallet=wallet).order_by('-created_at')[:max_rows]

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
    """Export PDF des transactions portefeuille (mémoire tampon, sans écriture disque)."""
    from django.http import HttpResponse
    from io import BytesIO

    max_rows = getattr(settings, 'MAX_EXPORT_ROWS', 1000)
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at')[:max_rows]

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
        c.drawString(
            50,
            y,
            f'Utilisateur : {request.user.get_full_name() or request.user.username}',
        )
        y -= 16
        c.drawString(50, y, f'Solde actuel : {wallet.balance} FCFA')
        y -= 24
        for tx in transactions:
            if y < 60:
                c.showPage()
                y = 800
            line = (
                f'{tx.created_at:%Y-%m-%d %H:%M} | {tx.transaction_type} | '
                f'{tx.amount} FCFA | {(tx.description or "")[:40]}'
            )
            c.drawString(50, y, line)
            y -= 14
        c.save()
        pdf_bytes = buffer.getvalue()
    except ImportError:
        pdf_bytes = b'%PDF-1.4\nReleve FONACO - reportlab requis\n'

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="releve_fonaco.pdf"'
    response['Content-Length'] = str(len(pdf_bytes))
    return response
