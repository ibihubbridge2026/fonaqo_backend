from django.contrib import admin
from .models import Opportunity, OpportunityApplication, OpportunityMatch


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    """Admin configuration pour les opportunités"""
    
    list_display = [
        'title', 'type', 'status', 'priority', 
        'client', 'assigned_agent', 'estimated_price',
        'created_at', 'expires_at'
    ]
    list_filter = [
        'status', 'type', 'priority', 'created_at',
        'expires_at', 'client'
    ]
    search_fields = ['title', 'description', 'client__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('title', 'description', 'type', 'status', 'priority')
        }),
        ('Localisation', {
            'fields': (
                'pickup_address', 'pickup_latitude', 'pickup_longitude',
                'delivery_address', 'delivery_latitude', 'delivery_longitude'
            )
        }),
        ('Budget', {
            'fields': ('budget_min', 'budget_max', 'fixed_price')
        }),
        ('Délais', {
            'fields': ('start_date', 'end_date', 'estimated_duration', 'expires_at')
        }),
        ('Assignation', {
            'fields': ('client', 'assigned_agent', 'required_skills')
        }),
        ('Feedback', {
            'fields': ('client_notes', 'agent_feedback', 'rating')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def estimated_price(self, obj):
        """Affiche le prix estimé formaté"""
        price = obj.estimated_price
        if price:
            return f"{price:.0f} FCFA"
        return "Non spécifié"
    estimated_price.short_description = "Prix estimé"


@admin.register(OpportunityApplication)
class OpportunityApplicationAdmin(admin.ModelAdmin):
    """Admin configuration pour les candidatures"""
    
    list_display = [
        'opportunity', 'agent', 'status', 
        'proposed_price', 'created_at'
    ]
    list_filter = ['status', 'created_at', 'opportunity__type']
    search_fields = [
        'opportunity__title', 'agent__username', 
        'agent__email', 'message'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Candidature', {
            'fields': ('opportunity', 'agent', 'status', 'message')
        }),
        ('Proposition', {
            'fields': ('proposed_price',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(OpportunityMatch)
class OpportunityMatchAdmin(admin.ModelAdmin):
    """Admin configuration pour les matchs"""
    
    list_display = [
        'opportunity', 'agent', 'match_score',
        'distance_score', 'skills_score', 
        'availability_score', 'rating_score',
        'created_at'
    ]
    list_filter = ['match_score', 'created_at', 'opportunity__type']
    search_fields = [
        'opportunity__title', 'agent__username'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Matching', {
            'fields': ('opportunity', 'agent', 'match_score')
        }),
        ('Scores détaillés', {
            'fields': (
                'distance_score', 'skills_score',
                'availability_score', 'rating_score'
            )
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Rend les scores non modifiables après création"""
        if obj:  # Si l'objet existe déjà
            return self.readonly_fields + ['match_score', 'distance_score', 'skills_score', 'availability_score', 'rating_score']
        return self.readonly_fields
