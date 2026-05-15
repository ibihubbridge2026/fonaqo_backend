from rest_framework import serializers

from .models import Wallet, Transaction


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ('id', 'balance', 'escrow_balance', 'created_at', 'updated_at')
        read_only_fields = fields


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = (
            'id',
            'amount',
            'transaction_type',
            'status',
            'reference',
            'description',
            'created_at',
        )
        read_only_fields = fields
