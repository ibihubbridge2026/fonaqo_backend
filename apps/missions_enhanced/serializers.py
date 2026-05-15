from rest_framework import serializers
from .models import MissionProof, MissionTimelineEvent, AgentStatistics
from django.contrib.auth import get_user_model

User = get_user_model()


class MissionProofSerializer(serializers.ModelSerializer):
    """Serializer pour les preuves de mission"""
    uploaded_by = serializers.StringRelatedField(read_only=True)
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = MissionProof
        fields = [
            'id', 'mission', 'uploaded_by', 'image', 'image_url',
            'caption', 'is_primary', 'created_at',
            'location_lat', 'location_lng'
        ]
        read_only_fields = ['uploaded_by', 'created_at']
    
    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class MissionProofCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer des preuves de mission"""
    
    class Meta:
        model = MissionProof
        fields = [
            'mission', 'image', 'caption', 'is_primary',
            'location_lat', 'location_lng'
        ]
    
    def validate_mission(self, value):
        user = self.context['request'].user
        # Vérifier que l'utilisateur est l'agent assigné à la mission
        if hasattr(user, 'agentprofile'):
            if value.assigned_agent != user.agentprofile:
                raise serializers.ValidationError(
                    "Vous ne pouvez ajouter des preuves qu'à vos missions assignées"
                )
        else:
            raise serializers.ValidationError(
                "Seuls les agents peuvent ajouter des preuves"
            )
        return value
    
    def validate(self, data):
        if data.get('is_primary'):
            # Vérifier qu'il n'y a pas déjà une photo primaire
            mission = data.get('mission')
            existing_primary = MissionProof.objects.filter(
                mission=mission, is_primary=True
            ).exists()
            
            if existing_primary:
                raise serializers.ValidationError(
                    "Il y a déjà une photo primaire pour cette mission"
                )
        return data


class MissionTimelineEventSerializer(serializers.ModelSerializer):
    """Serializer pour les événements de timeline"""
    performed_by = serializers.StringRelatedField(read_only=True)
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    
    class Meta:
        model = MissionTimelineEvent
        fields = [
            'id', 'mission', 'event_type', 'event_type_display',
            'occurred_at', 'performed_by', 'notes',
            'location_lat', 'location_lng', 'metadata'
        ]
        read_only_fields = ['occurred_at', 'performed_by']


class MissionTimelineEventCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer des événements de timeline"""
    
    class Meta:
        model = MissionTimelineEvent
        fields = [
            'mission', 'event_type', 'notes',
            'location_lat', 'location_lng', 'metadata'
        ]
    
    def validate_mission(self, value):
        user = self.context['request'].user
        # Vérifier que l'utilisateur peut ajouter des événements
        if value.client == user or (hasattr(user, 'agentprofile') and value.assigned_agent == user.agentprofile):
            return value
        raise serializers.ValidationError(
            "Vous ne pouvez ajouter des événements qu'à vos missions"
        )


class AgentStatisticsSerializer(serializers.ModelSerializer):
    """Serializer pour les statistiques d'agent"""
    agent_name = serializers.SerializerMethodField()
    success_rate = serializers.ReadOnlyField()
    level = serializers.ReadOnlyField()
    
    class Meta:
        model = AgentStatistics
        fields = [
            'id', 'agent', 'agent_name',
            'total_missions', 'completed_missions', 'cancelled_missions',
            'total_earnings', 'current_month_earnings',
            'average_rating', 'total_ratings',
            'completion_rate', 'average_response_time',
            'total_active_hours', 'total_disputes', 'resolved_disputes',
            'current_streak_days', 'longest_streak_days',
            'success_rate', 'level',
            'last_updated', 'last_mission_date'
        ]
        read_only_fields = [
            'agent', 'last_updated', 'success_rate', 'level'
        ]
    
    def get_agent_name(self, obj):
        if obj.agent and obj.agent.user:
            return f"{obj.agent.user.first_name} {obj.agent.user.last_name}"
        return "Agent Inconnu"


class AgentDashboardStatsSerializer(serializers.Serializer):
    """Serializer pour les stats du dashboard agent"""
    # Stats aujourd'hui
    today_missions = serializers.IntegerField()
    today_earnings = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    # Stats cette semaine
    week_missions = serializers.IntegerField()
    week_earnings = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    # Stats ce mois
    month_missions = serializers.IntegerField()
    month_earnings = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    # Stats globales
    total_missions = serializers.IntegerField()
    total_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    completion_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    # Missions en cours
    active_missions = serializers.IntegerField()
    pending_missions = serializers.IntegerField()
    
    # Niveau et streak
    level = serializers.CharField()
    current_streak = serializers.IntegerField()


class MissionProofBulkCreateSerializer(serializers.Serializer):
    """Serializer pour créer plusieurs preuves en une fois"""
    mission_id = serializers.IntegerField()
    proofs = serializers.ListField(
        child=serializers.DictField(),
        help_text="Liste des preuves à créer. Chaque preuve doit contenir: image, caption, location_lat, location_lng"
    )
    
    def validate_proofs(self, value):
        if not value:
            raise serializers.ValidationError("Au moins une preuve est requise")
        
        for i, proof in enumerate(value):
            if 'image' not in proof:
                raise serializers.ValidationError(
                    f"L'image est requise pour la preuve {i+1}"
                )
        return value
