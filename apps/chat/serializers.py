from rest_framework import serializers
from .models import Message


class MessageSerializer(serializers.ModelSerializer):
    """Serializer pour les messages du chat."""
    
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    recipient_name = serializers.CharField(source='recipient.username', read_only=True)
    
    class Meta:
        model = Message
        fields = (
            'id',
            'content',
            'timestamp',
            'is_read',
            'sender',
            'recipient',
            'sender_name',
            'recipient_name',
            'mission',
        )
        read_only_fields = ('sender', 'timestamp')


class MessageCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer un nouveau message."""
    
    class Meta:
        model = Message
        fields = ('content', 'recipient', 'mission')
    
    def create(self, validated_data):
        # L'expéditeur est toujours l'utilisateur connecté
        validated_data['sender'] = self.context['request'].user
        return super().create(validated_data)
