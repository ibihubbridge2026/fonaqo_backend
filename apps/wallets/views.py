from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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
    """Retourne l'historique des transactions de l'utilisateur."""
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    transactions = Transaction.objects.filter(wallet=wallet)[:50]
    serializer = TransactionSerializer(transactions, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
