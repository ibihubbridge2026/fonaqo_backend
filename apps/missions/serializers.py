from rest_framework_gis.serializers import GeoFeatureModelSerializer
from rest_framework import serializers
from .models import Mission

class MissionSerializer(GeoFeatureModelSerializer):
    client_phone = serializers.ReadOnlyField(source='client.phone_number')
    agent_name = serializers.ReadOnlyField(source='agent.username')
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Indispensable pour que Flutter puisse afficher l'image de preuve
    end_photo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Mission
        geo_field = "location"
        fields = (
            'id', 'client', 'client_phone', 'agent', 'agent_name',
            'title', 'description', 'price', 'status', 'status_display',
            'address', 'qr_code_token', 'end_photo', 'created_at'
        )
        # On met le token en lecture seule pour que seul le backend le génère
        read_only_fields = ('status', 'qr_code_token', 'agent')