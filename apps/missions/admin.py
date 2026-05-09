from django.contrib.gis import admin
from django.db.models import Sum, Count, Q
from .models import Mission, MissionTimeline, AgentLevel, Tag, Dispute, BoostPlan

class MissionStats(Mission):
    class Meta:
        proxy = True
        verbose_name = '💰 Tableau de Bord Financier'
        verbose_name_plural = '💰 Tableaux de Bord Financiers'

@admin.register(MissionStats)
class MissionStatsAdmin(admin.ModelAdmin):
    change_list_template = 'admin/mission_stats_change_list.html'

    def changelist_view(self, request, extra_context=None):
        stats = Mission.objects.aggregate(
            total_volume=Sum('price'),
            total_revenue=Sum('service_fee'),
            mission_count=Count('id'),
            escrow_locked=Sum('price', filter=Q(status='ACCEPTED'))
        )
        extra_context = extra_context or {}
        extra_context['summary'] = stats
        return super().changelist_view(request, extra_context=extra_context)

@admin.register(Mission)
class MissionAdmin(admin.GISModelAdmin): 
    list_display = ('title', 'client', 'agent', 'status', 'price', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'client__phone_number', 'agent__phone_number')
    default_lat = 6.3671 
    default_lon = 2.4252
    default_zoom = 12

admin.site.register(MissionTimeline)
admin.site.register(AgentLevel)
admin.site.register(Tag)
admin.site.register(Dispute)
admin.site.register(BoostPlan)