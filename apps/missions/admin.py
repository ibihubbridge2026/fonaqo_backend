from django.contrib import admin
from django.utils import timezone

from apps.escrow.services import EscrowService

from .models import MaterialWithdrawalRequest, Mission


@admin.register(MaterialWithdrawalRequest)
class MaterialWithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'mission', 'amount', 'status', 'created_at', 'reviewed_at')
    list_filter = ('status',)
    search_fields = ('mission__id', 'mission__title')
    readonly_fields = ('created_at', 'reviewed_at')

    def save_model(self, request, obj, form, change):
        previous_status = None
        if obj.pk:
            previous_status = MaterialWithdrawalRequest.objects.filter(
                pk=obj.pk,
            ).values_list('status', flat=True).first()

        super().save_model(request, obj, form, change)

        if (
            obj.status == MaterialWithdrawalRequest.Status.APPROVED
            and previous_status != MaterialWithdrawalRequest.Status.APPROVED
        ):
            EscrowService.release_material_to_agent(obj.mission, obj.amount)
            obj.reviewed_at = timezone.now()
            MaterialWithdrawalRequest.objects.filter(pk=obj.pk).update(
                reviewed_at=obj.reviewed_at,
            )


@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'client', 'agent', 'labor_cost', 'material_cost', 'price')
    list_filter = ('status',)
    search_fields = ('title', 'id')
