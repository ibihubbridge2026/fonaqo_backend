import uuid
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import WithdrawalRequestSerializer, WithdrawalResponseSerializer
from apps.wallets.models import Wallet, Transaction
from apps.core.choices import TransactionStatus


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

        # Récupérer ou créer le wallet
        wallet, _ = Wallet.objects.get_or_create(user=user)

        # Déduire le montant du solde
        wallet.balance -= amount
        wallet.save()

        # Créer la transaction de retrait
        transaction = Transaction.objects.create(
            wallet=wallet,
            amount=amount,
            transaction_type=Transaction.TransactionType.WITHDRAWAL,
            status=TransactionStatus.PENDING,
            reference=f"WDR-{uuid.uuid4().hex[:12].upper()}",
            description=f"Retrait via {channel}"
        )

        response_data = {
            'transaction_id': str(transaction.id),
            'amount': float(transaction.amount),
            'channel': channel,
            'status': transaction.status,
            'message': 'Demande de retrait enregistrée avec succès'
        }

        response_serializer = WithdrawalResponseSerializer(response_data)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )
