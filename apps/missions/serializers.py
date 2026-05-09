from rest_framework_gis.serializers import GeoFeatureModelSerializer
from rest_framework import serializers
from .models import Mission, MissionTimeline, Tag
from django.contrib.humanize.templatetags.humanize import naturaltime

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('name', 'slug')

class MissionTimelineSerializer(serializers.ModelSerializer):
    """Pour afficher l'historique des étapes dans Flutter"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    time_ago = serializers.SerializerMethodField()
    author_name = serializers.ReadOnlyField(source='created_by.username')

    class Meta:
        model = MissionTimeline
        fields = ('status', 'status_display', 'message', 'time_ago', 'author_name', 'created_at')

    def get_time_ago(self, obj):
        return naturaltime(obj.created_at)

class MissionSerializer(GeoFeatureModelSerializer):
    # Infos acteurs
    client_phone = serializers.ReadOnlyField(source='client.phone_number')
    agent_name = serializers.ReadOnlyField(source='agent.username')
    agent_phone = serializers.ReadOnlyField(source='agent.phone_number')
    
    # Statuts et Tags
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    
    # Timeline et Distance (Point 1 & 4)
    timeline = MissionTimelineSerializer(many=True, read_only=True)
    distance = serializers.SerializerMethodField()
    
    # Médias
    end_photo = serializers.ImageField(required=False, allow_null=True)
    start_photo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Mission
        # GeoFeatureModelSerializer transforme 'location' en format GeoJSON
        geo_field = "location"
        fields = (
            'id', 'client', 'client_phone', 'agent', 'agent_name', 'agent_phone',
            'title', 'description', 'price', 'service_fee', 'status', 'status_display',
            'address', 'qr_code_token', 'start_photo', 'end_photo', 
            'tags', 'timeline', 'distance', 'created_at'
        )
        read_only_fields = ('status', 'qr_code_token', 'agent', 'service_fee')

    def get_distance(self, obj):
        """
        Retourne la distance entre l'utilisateur et la mission.
        Nécessite que 'distance' soit annoté dans le QuerySet de la View.
        """
        if hasattr(obj, 'distance'):
            # Convertit la distance en mètres ou km lisibles
            dist = obj.distance.m
            if dist > 1000:
                return f"{round(dist / 1000, 1)} km"
            return f"{int(dist)} m"
        return None