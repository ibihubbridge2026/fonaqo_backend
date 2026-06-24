from django.contrib import admin
from .models import BoostPlan, AgentBoost, BoostPromotion


@admin.register(BoostPlan)
class BoostPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'duration_hours', 'price', 'visibility_multiplier', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['price']


@admin.register(AgentBoost)
class AgentBoostAdmin(admin.ModelAdmin):
    list_display = ['agent', 'plan', 'status', 'started_at', 'expires_at', 'purchase_amount']
    list_filter = ['status', 'started_at', 'expires_at']
    search_fields = ['agent__username', 'agent__email', 'plan__name']
    ordering = ['-started_at']
    readonly_fields = ['started_at', 'created_at', 'updated_at']


@admin.register(BoostPromotion)
class BoostPromotionAdmin(admin.ModelAdmin):
    list_display = ['boost_plan', 'discount_percentage', 'start_date', 'end_date', 'is_active', 'is_currently_active']
    list_filter = ['is_active', 'start_date', 'end_date']
    search_fields = ['boost_plan__name']
    ordering = ['-start_date']
    readonly_fields = ['is_currently_active', 'get_discounted_price', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Plan de boost', {
            'fields': ('boost_plan',)
        }),
        ('Réduction', {
            'fields': ('discount_percentage',)
        }),
        ('Période de validité', {
            'fields': ('start_date', 'end_date', 'is_active')
        }),
        ('Informations calculées', {
            'fields': ('is_currently_active', 'get_discounted_price'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
