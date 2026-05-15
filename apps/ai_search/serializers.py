from rest_framework import serializers
from .models import AISearchQuery, AISearchSuggestion


class AISearchQuerySerializer(serializers.ModelSerializer):
    """Serializer pour les requêtes de recherche IA"""
    
    class Meta:
        model = AISearchQuery
        fields = ['id', 'query', 'response', 'created_at']
        read_only_fields = ['id', 'created_at']


class AISearchSuggestionSerializer(serializers.ModelSerializer):
    """Serializer pour les suggestions de recherche IA"""
    
    class Meta:
        model = AISearchSuggestion
        fields = ['id', 'query', 'suggestion', 'frequency', 'last_used']
        read_only_fields = ['id', 'frequency', 'last_used']
