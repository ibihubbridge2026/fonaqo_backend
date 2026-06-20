"""Serializers pour le système de notation."""

from rest_framework import serializers
from .models import Rating


class RatingSerializer(serializers.ModelSerializer):
    """Serializer pour création/lecture de notation."""

    class Meta:
        model = Rating
        fields = [
            'id',
            'mission',
            'reviewer',
            'reviewee',
            'rating_type',
            'score',
            'comment',
            'created_at',
        ]
        read_only_fields = ['id', 'reviewer', 'reviewee', 'created_at']

    def validate_score(self, value):
        """Valide que le score est entre 1 et 5."""
        if not 1 <= value <= 5:
            raise serializers.ValidationError("La note doit être entre 1 et 5.")
        return value
