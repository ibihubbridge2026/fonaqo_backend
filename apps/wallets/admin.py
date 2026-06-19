from django.contrib import admin
from .models import Wallet, Transaction, PayoutRequest

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'escrow_balance', 'created_at')
    search_fields = ('user__phone_number', 'user__username')
    readonly_fields = ('id', 'created_at', 'updated_at')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'transaction_type', 'amount', 'status', 'created_at')
    list_filter = ('transaction_type', 'status', 'created_at')
    search_fields = ('reference', 'wallet__user__phone_number')
    readonly_fields = ('id', 'created_at')


@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'wallet', 'amount', 'status', 'payment_method',
        'phone_number', 'created_at', 'processed_at',
    )
    list_filter = ('status', 'payment_method')
    search_fields = ('wallet__user__username', 'phone_number')
    readonly_fields = ('id', 'created_at', 'updated_at', 'processed_at')
    raw_id_fields = ('wallet', 'ledger_transaction', 'processed_by')