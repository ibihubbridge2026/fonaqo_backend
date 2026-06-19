import logging

from decimal import Decimal, InvalidOperation

from django.conf import settings
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.choices import TransactionStatus

from .models import Payment
from .serializers import WithdrawalRequestSerializer, WithdrawalResponseSerializer
from .services import FeexPayService, _quantize_fcfa
from apps.wallets.models import Wallet, Transaction

logger = logging.getLogger(__name__)


class WithdrawalViewSet(viewsets.ViewSet):
    """ViewSet pour les demandes de retrait"""
    permission_classes = [IsAuthenticated]

    def create(self, request):
        """Crée une demande de retrait"""
        serializer = WithdrawalRequestSerializer(
            data=request.data,
            context={'request': request}
        )

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        amount = serializer.validated_data['amount']
        channel = serializer.validated_data['channel']
        user = request.user

        from apps.wallets.payout_service import PayoutService, PayoutServiceError

        wallet, _ = Wallet.objects.get_or_create(user=user)
        phone = getattr(user, 'phone_number', '') or ''

        try:
            payout = PayoutService.request_withdrawal(
                wallet=wallet,
                amount=amount,
                payment_method=channel,
                phone_number=phone,
            )
        except PayoutServiceError as exc:
            return Response(
                {'message': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_data = {
            'transaction_id': str(payout.id),
            'payout_id': str(payout.id),
            'amount': float(payout.amount),
            'channel': channel,
            'status': payout.status,
            'message': 'Demande de retrait enregistrée avec succès',
        }

        response_serializer = WithdrawalResponseSerializer(response_data)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def feexpay_init_view(request):
    """Initialise un paiement FeexPay (wallet, boost, etc.)."""
    raw_amount = request.data.get('amount')
    purpose = request.data.get('purpose', Payment.Purpose.WALLET_DEPOSIT)
    payment_method = request.data.get('payment_method', 'MTN')
    metadata = request.data.get('metadata') or {}

    if raw_amount is None:
        return Response(
            {'message': 'Le montant est requis'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        amount = _quantize_fcfa(raw_amount)
    except (InvalidOperation, TypeError, ValueError):
        return Response(
            {'message': 'Montant invalide'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if amount <= 0:
        return Response(
            {'message': 'Le montant doit être positif'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    valid_purposes = {c[0] for c in Payment.Purpose.choices}
    if purpose not in valid_purposes:
        return Response(
            {'message': 'Objectif de paiement invalide'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payment = FeexPayService.init_payment(
        user=request.user,
        amount=amount,
        purpose=purpose,
        metadata=metadata,
        payment_method=payment_method,
    )

    return Response(
        {
            'payment_id': str(payment.id),
            'amount': int(payment.amount),
            'external_reference': payment.external_reference,
            'status': payment.status,
            'purpose': payment.purpose,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def feexpay_confirm_view(request):
    """
    Confirme un paiement FeexPay (sandbox / après retour SDK).
    En production, le webhook applique le crédit automatiquement.
    """
    if not getattr(settings, 'FEEXPAY_SANDBOX', True):
        return Response(
            {'message': 'Confirmation manuelle désactivée hors sandbox'},
            status=status.HTTP_403_FORBIDDEN,
        )

    payment_id = request.data.get('payment_id')
    external_reference = request.data.get('external_reference')

    payment = None
    if payment_id:
        payment = Payment.objects.filter(
            pk=payment_id, user=request.user,
        ).first()
    if payment is None and external_reference:
        payment = Payment.objects.filter(
            external_reference=external_reference, user=request.user,
        ).first()

    if payment is None:
        return Response(
            {'message': 'Paiement introuvable'},
            status=status.HTTP_404_NOT_FOUND,
        )

    payment = FeexPayService.apply_success(
        payment, feex_reference=external_reference,
    )

    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    return Response(
        {
            'payment_id': str(payment.id),
            'external_reference': payment.external_reference,
            'status': payment.status,
            'new_balance': int(wallet.balance),
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def feexpay_webhook_view(request):
    """Webhook FeexPay — met à jour les balances instantanément en cas de succès."""
    secret = getattr(settings, 'FEEXPAY_WEBHOOK_SECRET', '')
    if secret:
        incoming = request.headers.get('X-FeexPay-Signature', '')
        if incoming != secret:
            return Response(
                {'message': 'Signature invalide'},
                status=status.HTTP_403_FORBIDDEN,
            )

    payload = request.data if isinstance(request.data, dict) else {}
    payment = FeexPayService.handle_webhook(payload)
    if payment is None:
        return Response({'message': 'Ignoré'}, status=status.HTTP_200_OK)

    return Response(
        {
            'message': 'Paiement traité',
            'payment_id': str(payment.id),
            'status': payment.status,
        },
        status=status.HTTP_200_OK,
    )
