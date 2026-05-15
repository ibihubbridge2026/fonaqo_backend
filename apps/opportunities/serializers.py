from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Opportunity, OpportunityApplication, OpportunityMatch

User = get_user_model()


class OpportunitySerializer(serializers.ModelSerializer):
    """Serializer principal pour les opportunités"""
    
    client_name = serializers.CharField(source='client.get_full_name', read_only=True)
    client_avatar = serializers.CharField(source='client.avatar_url', read_only=True)
    assigned_agent_name = serializers.CharField(source='assigned_agent.get_full_name', read_only=True)
    estimated_price_display = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    
    class Meta:
        model = Opportunity
        fields = [
            'id', 'title', 'description', 'type', 'status', 'priority',
            'pickup_address', 'pickup_latitude', 'pickup_longitude',
            'delivery_address', 'delivery_latitude', 'delivery_longitude',
            'budget_min', 'budget_max', 'fixed_price', 'estimated_price_display',
            'start_date', 'end_date', 'estimated_duration',
            'client', 'client_name', 'client_avatar',
            'assigned_agent', 'assigned_agent_name',
            'required_skills', 'client_notes', 'agent_feedback', 'rating',
            'created_at', 'updated_at', 'expires_at',
            'time_remaining', 'is_available'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'client', 'assigned_agent']
    
    def get_estimated_price_display(self, obj):
        """Retourne le prix formaté pour l'affichage"""
        price = obj.estimated_price
        if price:
            return f"{price:.0f} FCFA"
        return "Non spécifié"
    
    def get_time_remaining(self, obj):
        """Retourne le temps restant avant expiration"""
        if obj.expires_at:
            from django.utils import timezone
            remaining = obj.expires_at - timezone.now()
            if remaining.total_seconds() > 0:
                hours = remaining.total_seconds() // 3600
                if hours < 24:
                    return f"{int(hours)}h"
                else:
                    days = hours // 24
                    return f"{int(days)}j"
            return "Expirée"
        return None
    
    def get_is_available(self, obj):
        """Vérifie si l'opportunité est disponible"""
        return obj.can_be_assigned


class OpportunityCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'opportunités"""
    
    class Meta:
        model = Opportunity
        fields = [
            'title', 'description', 'type', 'priority',
            'pickup_address', 'pickup_latitude', 'pickup_longitude',
            'delivery_address', 'delivery_latitude', 'delivery_longitude',
            'budget_min', 'budget_max', 'fixed_price',
            'start_date', 'end_date', 'estimated_duration',
            'expires_at', 'required_skills', 'client_notes'
        ]
    
    def validate(self, data):
        """Validation des données d'opportunité"""
        # Vérifier qu'au moins un type de prix est spécifié
        if not data.get('fixed_price') and not (data.get('budget_min') and data.get('budget_max')):
            raise serializers.ValidationError(
                "Spécifiez soit un prix fixe, soit une fourchette de budget"
            )
        
        # Vérifier la cohérence du budget
        budget_min = data.get('budget_min')
        budget_max = data.get('budget_max')
        if budget_min and budget_max and budget_min > budget_max:
            raise serializers.ValidationError(
                "Le budget minimum ne peut pas être supérieur au budget maximum"
            )
        
        return data


class OpportunityApplicationSerializer(serializers.ModelSerializer):
    """Serializer pour les candidatures"""
    
    agent_name = serializers.CharField(source='agent.get_full_name', read_only=True)
    agent_avatar = serializers.CharField(source='agent.avatar_url', read_only=True)
    agent_rating = serializers.SerializerMethodField()
    opportunity_title = serializers.CharField(source='opportunity.title', read_only=True)
    
    class Meta:
        model = OpportunityApplication
        fields = [
            'id', 'opportunity', 'opportunity_title', 'agent', 'agent_name', 
            'agent_avatar', 'agent_rating', 'status', 'message', 'proposed_price',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'opportunity', 'agent']
    
    def get_agent_rating(self, obj):
        """Retourne la note moyenne de l'agent"""
        # TODO: Implémenter le calcul de la note moyenne
        return 4.5  # Temporaire


class OpportunityMatchSerializer(serializers.ModelSerializer):
    """Serializer pour les matchs d'opportunités"""
    
    opportunity_title = serializers.CharField(source='opportunity.title', read_only=True)
    opportunity_type = serializers.CharField(source='opportunity.type', read_only=True)
    opportunity_priority = serializers.CharField(source='opportunity.priority', read_only=True)
    estimated_price = serializers.SerializerMethodField()
    
    agent_name = serializers.CharField(source='agent.get_full_name', read_only=True)
    agent_avatar = serializers.CharField(source='agent.avatar_url', read_only=True)
    agent_rating = serializers.SerializerMethodField()
    
    class Meta:
        model = OpportunityMatch
        fields = [
            'id', 'opportunity', 'opportunity_title', 'opportunity_type', 
            'opportunity_priority', 'estimated_price',
            'agent', 'agent_name', 'agent_avatar', 'agent_rating',
            'match_score', 'distance_score', 'skills_score', 
            'availability_score', 'rating_score',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_estimated_price(self, obj):
        """Retourne le prix estimé formaté"""
        price = obj.opportunity.estimated_price
        if price:
            return f"{price:.0f} FCFA"
        return "Non spécifié"
    
    def get_agent_rating(self, obj):
        """Retourne la note moyenne de l'agent"""
        # TODO: Implémenter le calcul de la note moyenne
        return 4.5  # Temporaire


class OpportunityListSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour les listes d'opportunités"""
    
    client_name = serializers.CharField(source='client.get_full_name', read_only=True)
    estimated_price_display = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    distance_km = serializers.SerializerMethodField()
    
    class Meta:
        model = Opportunity
        fields = [
            'id', 'title', 'type', 'priority', 'status',
            'pickup_address', 'estimated_price_display', 'time_remaining',
            'distance_km', 'client_name', 'created_at'
        ]
    
    def get_estimated_price_display(self, obj):
        price = obj.estimated_price
        if price:
            return f"{price:.0f} FCFA"
        return "Non spécifié"
    
    def get_time_remaining(self, obj):
        if obj.expires_at:
            from django.utils import timezone
            remaining = obj.expires_at - timezone.now()
            if remaining.total_seconds() > 0:
                hours = remaining.total_seconds() // 3600
                if hours < 24:
                    return f"{int(hours)}h"
                else:
                    days = hours // 24
                    return f"{int(days)}j"
            return "Expirée"
        return None
    
    def get_distance_km(self, obj):
        """Calcule la distance depuis la position actuelle de l'agent"""
        # TODO: Implémenter le calcul de distance réel
        return "2.3 km"  # Temporaire
