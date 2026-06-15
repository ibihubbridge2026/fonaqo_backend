from rest_framework import serializers
from .models import Dispute, DisputeEvidence, DisputeComment
from apps.missions.serializers import MissionDetailSerializer as MissionSerializer
from django.contrib.auth import get_user_model

User = get_user_model()


class DisputeEvidenceSerializer(serializers.ModelSerializer):
    """Serializer pour les preuves de litige"""
    uploaded_by = serializers.StringRelatedField(read_only=True)
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = DisputeEvidence
        fields = [
            'id', 'dispute', 'uploaded_by', 'file', 'file_url',
            'description', 'created_at'
        ]
        read_only_fields = ['uploaded_by', 'created_at']
    
    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class DisputeCommentSerializer(serializers.ModelSerializer):
    """Serializer pour les commentaires de litige"""
    author = serializers.StringRelatedField(read_only=True)
    author_id = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = DisputeComment
        fields = [
            'id', 'dispute', 'author', 'author_id', 'comment',
            'is_internal', 'created_at', 'edited_at'
        ]
        read_only_fields = ['author', 'created_at', 'edited_at']


class DisputeSerializer(serializers.ModelSerializer):
    """Serializer principal pour les litiges"""
    mission = MissionSerializer(read_only=True)
    mission_id = serializers.IntegerField(write_only=True)
    opened_by = serializers.StringRelatedField(read_only=True)
    assigned_to = serializers.StringRelatedField(read_only=True)
    evidences = DisputeEvidenceSerializer(many=True, read_only=True)
    comments = DisputeCommentSerializer(many=True, read_only=True)
    is_open = serializers.ReadOnlyField()
    days_open = serializers.ReadOnlyField()
    evidence_file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Dispute
        fields = [
            'id', 'mission', 'mission_id', 'opened_by', 'assigned_to',
            'title', 'description', 'evidence_file', 'evidence_file_url',
            'status', 'priority',
            'resolution_notes', 'resolved_at', 'resolved_by',
            'refund_amount', 'penalty_amount',
            'evidences', 'comments', 'is_open', 'days_open',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'opened_by', 'resolved_at', 'resolved_by',
            'is_open', 'days_open', 'created_at', 'updated_at'
        ]

    def get_evidence_file_url(self, obj):
        if obj.evidence_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.evidence_file.url)
            return obj.evidence_file.url
        return None


class DisputeCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer un nouveau litige"""
    
    class Meta:
        model = Dispute
        fields = [
            'mission', 'title', 'description', 'priority', 'evidence_file'
        ]
    
    def validate_mission(self, value):
        user = self.context['request'].user
        # Vérifier que l'utilisateur peut créer un litige sur cette mission
        if value.client != user and not hasattr(user, 'agentprofile'):
            raise serializers.ValidationError(
                "Vous ne pouvez créer un litige que sur vos propres missions"
            )
        return value


class DisputeResolveSerializer(serializers.ModelSerializer):
    """Serializer pour résoudre un litige (admin uniquement)"""
    
    class Meta:
        model = Dispute
        fields = [
            'status', 'resolution_notes', 'refund_amount', 'penalty_amount'
        ]
    
    def validate_status(self, value):
        if value not in ['resolved', 'closed']:
            raise serializers.ValidationError(
                "Le statut doit être 'resolved' ou 'closed'"
            )
        return value


class DisputeEvidenceCreateSerializer(serializers.ModelSerializer):
    """Serializer pour ajouter une preuve à un litige"""
    
    class Meta:
        model = DisputeEvidence
        fields = [
            'dispute', 'file', 'description'
        ]
    
    def validate_dispute(self, value):
        user = self.context['request'].user
        if value.opened_by != user and not user.is_staff:
            raise serializers.ValidationError(
                "Vous ne pouvez ajouter des preuves qu'à vos propres litiges"
            )
        return value
