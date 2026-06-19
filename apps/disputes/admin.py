from django.contrib import admin

from .models import Dispute, DisputeEvidence, DisputeComment
from .services import notify_dispute_resolution


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'title', 'mission', 'status', 'priority',
        'opened_by', 'assigned_to', 'created_at',
    )
    list_filter = ('status', 'priority')
    search_fields = ('title', 'mission__title', 'mission__id')
    readonly_fields = ('created_at', 'updated_at', 'resolved_at')
    raw_id_fields = ('mission', 'opened_by', 'assigned_to', 'resolved_by')

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change and obj.pk:
            previous_status = (
                Dispute.objects.filter(pk=obj.pk)
                .values_list('status', flat=True)
                .first()
            )
        super().save_model(request, obj, form, change)
        resolved_statuses = {'resolved', 'closed'}
        if obj.status in resolved_statuses and previous_status not in resolved_statuses:
            if not obj.resolved_by_id:
                obj.resolved_by = request.user
            from django.utils import timezone
            if not obj.resolved_at:
                obj.resolved_at = timezone.now()
            obj.save(update_fields=['resolved_by', 'resolved_at', 'updated_at'])
            notify_dispute_resolution(obj)


@admin.register(DisputeEvidence)
class DisputeEvidenceAdmin(admin.ModelAdmin):
    list_display = ('dispute', 'uploaded_by', 'created_at')
    raw_id_fields = ('dispute', 'uploaded_by')


@admin.register(DisputeComment)
class DisputeCommentAdmin(admin.ModelAdmin):
    list_display = ('dispute', 'author', 'is_internal', 'created_at')
    raw_id_fields = ('dispute', 'author')
