from django.contrib import admin

from .models import AdminAuditLog, AdminNotification, PlatformConfiguration
from .services import PlatformConfigService


@admin.register(PlatformConfiguration)
class PlatformConfigurationAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'description', 'updated_at')
    search_fields = ('key', 'description')
    ordering = ('key',)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        PlatformConfigService.invalidate(obj.key)


@admin.register(AdminNotification)
class AdminNotificationAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'category', 'severity', 'is_read', 'mission', 'created_at',
    )
    list_filter = ('category', 'severity', 'is_read')
    search_fields = ('title', 'message')
    readonly_fields = ('created_at',)
    raw_id_fields = ('mission',)


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'admin', 'target_type', 'target_id', 'created_at')
    list_filter = ('action', 'target_type')
    search_fields = ('action', 'detail', 'target_id')
    readonly_fields = ('created_at',)
    raw_id_fields = ('admin',)
