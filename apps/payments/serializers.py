from rest_framework import serializers
from django.conf import settings
from apps.wallets.models import Wallet, Transaction
from apps.core.choices import TransactionStatus


class WithdrawalRequestSerializer(serializers.Serializer):
    """Serializer pour les demandes de retrait"""
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        error_messages={
            'required': 'Le montant est obligatoire.',
            'invalid': 'Le montant doit être un nombre valide.',
            'max_digits': 'Le montant est trop élevé.',
            'max_decimal_places': 'Le montant ne peut avoir que 2 décimales.'
        }
    )
    channel = serializers.ChoiceField(
        choices=['MTN_MOMO', 'MOOV_FLOOZ'],
        error_messages={
            'required': 'Le canal de paiement est obligatoire.',
            'invalid_choice': 'Le canal doit être MTN_MOMO ou MOOV_FLOOZ.'
        }
    )

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le montant doit être supérieur à 0.")
        return value

    def validate(self, attrs):
        user = self.context['request'].user
        wallet, _ = Wallet.objects.get_or_create(user=user)
        
        if wallet.balance < attrs['amount']:
            raise serializers.ValidationError(
                {"amount": "Solde insuffisant pour ce retrait."}
            )
        return attrs


class WithdrawalResponseSerializer(serializers.Serializer):
    """Serializer pour la réponse de retrait"""
    transaction_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    channel = serializers.CharField()
    status = serializers.CharField()
    message = serializers.CharField()
