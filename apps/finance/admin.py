from django.contrib import admin

from .models import LedgerEntry, LedgerReconciliationRun


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = (
        'occurred_at', 'entry_type', 'reference', 'amount',
        'debit_account', 'credit_account',
    )
    list_filter = ('entry_type', 'occurred_at')
    search_fields = ('reference', 'description', 'debit_account', 'credit_account')
    readonly_fields = (
        'id', 'entry_type', 'reference', 'occurred_at',
        'debit_account', 'credit_account', 'amount', 'currency',
        'transaction_id', 'user_id', 'mission_id',
        'description', 'metadata', 'created_by', 'source_ip',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LedgerReconciliationRun)
class LedgerReconciliationRunAdmin(admin.ModelAdmin):
    list_display = ('run_at', 'status', 'wallets_checked', 'mismatches_count', 'duration_ms')
    list_filter = ('status',)
    readonly_fields = (
        'id', 'run_at', 'status', 'wallets_checked', 'mismatches_count',
        'mismatch_details', 'duration_ms', 'error_message',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
