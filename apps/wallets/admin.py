from django.contrib import admin
from .models import Wallet, Transaction

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'escrow_balance', 'created_at')
    search_fields = ('user__phone_number', 'user__username')
    readonly_fields = ('id', 'created_at', 'updated_at')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'transaction_type', 'amount', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('reference', 'wallet__user__phone_number')
    readonly_fields = ('id', 'created_at')