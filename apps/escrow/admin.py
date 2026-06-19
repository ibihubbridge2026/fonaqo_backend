from django.contrib import admin

from .models import Escrow, EscrowSplitRecord


@admin.register(Escrow)
class EscrowAdmin(admin.ModelAdmin):
    list_display = ('mission', 'amount', 'status', 'created_at', 'released_at')
    list_filter = ('status',)
    search_fields = ('mission__id', 'mission__title')
    readonly_fields = ('created_at', 'released_at')


@admin.register(EscrowSplitRecord)
class EscrowSplitRecordAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'mission',
        'beneficiary_type',
        'amount_fcfa',
        'beneficiary_user',
        'influencer',
    )
    list_filter = ('beneficiary_type', 'created_at')
    search_fields = ('mission__id', 'mission__title')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
