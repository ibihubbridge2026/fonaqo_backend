from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    # On utilise 'kyc_status' qui est dans ton modèle
    list_display = ('view_id_front', 'phone_number', 'email', 'is_agent', 'kyc_status', 'display_kyc_badge', 'date_joined')
    list_filter = ('is_agent', 'kyc_status', 'is_staff')
    search_fields = ('phone_number', 'email', 'username')
    
    fieldsets = (
        (None, {'fields': ('username',)}),
        ('Infos Personnelles', {'fields': ('phone_number', 'email', 'profile_picture')}),
        ('Rôles', {'fields': ('is_agent', 'is_client', 'is_staff', 'is_active')}),
        ('Vérification KYC (Agent)', {
            # J'ai ajouté 'kyc_status' ici pour que tu puisses le modifier manuellement
            'fields': ('is_verified', 'kyc_status', 'id_card_number', 'id_card_front', 'id_card_back', 'selfie_with_id'),
            'description': "Vérifiez soigneusement les photos avant de valider le KYC."
        }),
        ('Témoins / Urgence', {'fields': ('witness_1_name', 'witness_1_phone', 'witness_2_name', 'witness_2_phone')}),
    )

    @admin.display(description="Badge KYC")
    def display_kyc_badge(self, obj):
        # Utilisation de kyc_status pour le badge
        if obj.is_verified or obj.kyc_status == 'APPROVED': # Adapte selon tes KYCStatus choices
            return mark_safe('<b style="color:green;">VÉRIFIÉ</b>')
        if obj.kyc_status == 'PENDING':
            return mark_safe('<b style="color:orange;">EN ATTENTE</b>')
        return mark_safe('<b style="color:red;">NON VALIDE</b>')

    @admin.display(description="ID")
    def view_id_front(self, obj):
        if obj.id_card_front:
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" width="40" height="40" style="border-radius:50%; object-fit:cover; border:1px solid #ccc;" /></a>',
                obj.id_card_front.url
            )
        return "-"