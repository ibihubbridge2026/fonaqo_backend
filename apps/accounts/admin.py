from django.contrib import admin
from django.utils.html import format_html
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    # Colonnes affichées dans la liste
    list_display = ('phone_number', 'email', 'is_agent', 'is_verified', 'display_kyc_status', 'date_joined')
    list_filter = ('is_agent', 'is_verified', 'is_staff')
    search_fields = ('phone_number', 'email', 'username')
    
    # Organisation des champs dans le formulaire de modification
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Infos Personnelles', {'fields': ('phone_number', 'email', 'profile_picture')}),
        ('Rôles', {'fields': ('is_agent', 'is_client', 'is_staff', 'is_active')}),
        ('Vérification KYC (Agent)', {
            'fields': ('is_verified', 'id_card_number', 'id_card_front', 'id_card_back', 'selfie_with_id'),
            'description': "Vérifiez soigneusement les photos avant de cocher 'Is Verified'."
        }),
        ('Témoins / Urgence', {'fields': ('witness_1_name', 'witness_1_phone', 'witness_2_name', 'witness_2_phone')}),
    )

    def display_kyc_status(self, obj):
        """Affiche un badge visuel pour le statut de vérification"""
        if obj.is_verified:
            return format_html('<b style="color:green;">VÉRIFIÉ</b>')
        if obj.is_agent and not obj.is_verified:
            return format_html('<b style="color:orange;">EN ATTENTE</b>')
        return "-"
    display_kyc_status.short_description = "Statut KYC"

    # Optionnel : Afficher une miniature de la photo d'identité directement dans l'admin
    def view_id_front(self, obj):
        if obj.id_card_front:
            return format_html('<img src="{}" width="100" />', obj.id_card_front.url)
        return "Pas de photo"