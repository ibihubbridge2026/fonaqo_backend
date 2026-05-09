from django.contrib import admin
from django.utils.html import format_html
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    # Ajout de view_id_front dans list_display (déjà fait, c'est top)
    list_display = ('view_id_front', 'phone_number', 'email', 'is_agent', 'is_verified', 'display_kyc_status', 'date_joined')
    list_filter = ('is_agent', 'is_verified', 'is_staff')
    search_fields = ('phone_number', 'email', 'username')
    ordering = ('-date_joined',) # Les plus récents en premier
    
    fieldsets = (
        (None, {'fields': ('username',)}), # On enlève password d'ici pour la sécurité
        ('Infos Personnelles', {'fields': ('phone_number', 'email', 'profile_picture')}),
        ('Rôles', {'fields': ('is_agent', 'is_client', 'is_staff', 'is_active')}),
        ('Vérification KYC (Agent)', {
            'fields': ('is_verified', 'id_card_number', 'id_card_front', 'id_card_back', 'selfie_with_id'),
            'description': "Vérifiez soigneusement les photos avant de cocher 'Is Verified'."
        }),
        ('Témoins / Urgence', {'fields': ('witness_1_name', 'witness_1_phone', 'witness_2_name', 'witness_2_phone')}),
    )

    # --- MÉTHODES D'AFFICHAGE ---

    def display_kyc_status(self, obj):
        """Affiche un badge visuel pour le statut de vérification"""
        if obj.is_verified:
            return mark_safe('<b style="color:green;">VÉRIFIÉ</b>')
        if obj.is_agent and not obj.is_verified:
            return mark_safe('<b style="color:orange;">EN ATTENTE</b>')
        return "-"
    display_kyc_status.short_description = "Statut KYC"

    def view_id_front(self, obj):
        if obj.id_card_front:
            # On ajoute un lien cliquable pour voir l'image en grand, c'est plus pratique pour l'admin
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" width="80" style="border-radius:5px; border:1px solid #ccc;" /></a>',
                obj.id_card_front.url
            )
        return "Pas de photo"
    view_id_front.short_description = "Carte ID (Recto)"