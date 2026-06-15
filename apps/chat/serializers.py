from rest_framework import serializers
from .models import Conversation, Message, TypingStatus, ChatAttachment, UserPresence
from django.contrib.auth import get_user_model

User = get_user_model()


class TypingStatusSerializer(serializers.ModelSerializer):
    """Serializer pour le statut de frappe"""
    user = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = TypingStatus
        fields = ['id', 'conversation', 'user', 'is_typing', 'updated_at']
        read_only_fields = ['user', 'updated_at']


class ChatAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ChatAttachment
        fields = ['id', 'attachment_type', 'file', 'file_url',
                  'original_filename', 'file_size', 'mime_type', 'created_at']
        read_only_fields = ['created_at']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url


class UserPresenceSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = UserPresence
        fields = ['username', 'is_online', 'last_seen']


class MessageSerializer(serializers.ModelSerializer):
    """Serializer pour les messages"""
    sender = serializers.StringRelatedField(read_only=True)
    sender_id = serializers.IntegerField(read_only=True)
    media_file_url = serializers.SerializerMethodField()
    audio_file_url = serializers.SerializerMethodField()
    attachments = ChatAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = [
            'id', 'client_message_id', 'conversation', 'sender', 'sender_id',
            'message_type', 'content', 'proposed_price', 'negotiation_status',
            'media_file', 'media_file_url',
            'audio_file', 'audio_file_url', 'audio_duration',
            'delivery_status', 'is_read', 'read_at', 'delivered_at',
            'created_at', 'edited_at', 'is_deleted', 'attachments',
        ]
        read_only_fields = [
            'sender', 'delivery_status', 'is_read', 'read_at', 'delivered_at',
            'created_at', 'edited_at',
        ]
    
    def get_media_file_url(self, obj):
        if obj.media_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.media_file.url)
            return obj.media_file.url
        return None
    
    def get_audio_file_url(self, obj):
        if obj.audio_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.audio_file.url)
            return obj.audio_file.url
        return None


class MessageCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer un message (REST fallback — WebSocket est préféré)"""
    client_message_id = serializers.UUIDField(required=False, allow_null=True)
    proposed_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )

    class Meta:
        model = Message
        fields = [
            'conversation', 'client_message_id', 'message_type', 'content',
            'proposed_price', 'negotiation_status',
            'media_file', 'audio_file', 'audio_duration',
        ]
    
    def validate_conversation(self, value):
        user = self.context['request'].user
        if value.client != user and value.agent != user:
            raise serializers.ValidationError(
                "Vous ne pouvez envoyer des messages qu'à vos propres conversations"
            )
        return value
    
    def validate(self, data):
        message_type = data.get('message_type', 'text')
        
        if message_type == 'text' and not data.get('content'):
            raise serializers.ValidationError(
                "Le contenu est requis pour les messages texte"
            )
        
        if message_type == 'image' and not data.get('media_file'):
            raise serializers.ValidationError(
                "Un fichier image est requis pour les messages image"
            )
        
        if message_type == 'voice' and not data.get('audio_file'):
            raise serializers.ValidationError(
                "Un fichier audio est requis pour les messages vocaux"
            )

        if message_type == 'negotiation':
            user = self.context['request'].user
            conversation = data.get('conversation') or self.context.get('conversation')
            if conversation and conversation.agent != user:
                raise serializers.ValidationError(
                    "Seul l'agent peut proposer un nouveau tarif"
                )
            proposed = data.get('proposed_price')
            if proposed is None or proposed <= 0:
                raise serializers.ValidationError(
                    {'proposed_price': 'Un montant proposé valide est requis'}
                )
            data['negotiation_status'] = Message.NegotiationStatus.PENDING
            if not data.get('content'):
                data['content'] = f'Proposition tarif : {proposed} FCFA'

        return data


class ConversationSerializer(serializers.ModelSerializer):
    """Serializer pour les conversations"""
    client = serializers.SerializerMethodField()
    agent = serializers.SerializerMethodField()
    mission_title = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count_client = serializers.ReadOnlyField()
    unread_count_agent = serializers.ReadOnlyField()
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'mission', 'client', 'agent', 'mission_title',
            'created_at', 'updated_at', 'last_message_at',
            'is_archived', 'client_last_read', 'agent_last_read',
            'unread_count_client', 'unread_count_agent', 'last_message'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'last_message_at',
            'unread_count_client', 'unread_count_agent'
        ]
    
    def get_client(self, obj):
        if obj.client:
            return {
                'id': str(obj.client.id),
                'username': obj.client.username,
                'first_name': obj.client.first_name,
                'last_name': obj.client.last_name,
                'avatar_url': getattr(obj.client, 'avatar_url', None),
            }
        return None
    
    def get_agent(self, obj):
        if obj.agent:
            return {
                'id': str(obj.agent.id),
                'username': obj.agent.username,
                'first_name': obj.agent.first_name,
                'last_name': obj.agent.last_name,
                'avatar_url': getattr(obj.agent, 'avatar_url', None),
            }
        return None
    
    def get_mission_title(self, obj):
        if obj.mission:
            return obj.mission.title
        return "Conversation directe"
    
    def get_last_message(self, obj):
        last_message = obj.messages.last()
        if last_message:
            return MessageSerializer(last_message, context=self.context).data
        return None


class ConversationCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer une conversation"""
    
    class Meta:
        model = Conversation
        fields = ['mission', 'client', 'agent']
    
    def validate(self, data):
        user = self.context['request'].user
        client = data.get('client')
        agent = data.get('agent')
        
        # L'utilisateur doit être soit le client soit l'agent
        if user != client and user != agent:
            raise serializers.ValidationError(
                "Vous devez faire partie de la conversation"
            )
        
        # Vérifier qu'une conversation n'existe pas déjà
        mission = data.get('mission')
        existing = Conversation.objects.filter(
            mission=mission, client=client, agent=agent
        ).first()
        
        if existing:
            raise serializers.ValidationError(
                "Cette conversation existe déjà"
            )
        
        return data


class MessageMarkReadSerializer(serializers.Serializer):
    """Serializer pour marquer des messages comme lus"""
    message_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="Liste des IDs de messages à marquer comme lus"
    )
    mark_all = serializers.BooleanField(
        default=False,
        help_text="Marquer tous les messages non lus comme lus"
    )


class TypingStatusUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour mettre à jour le statut de frappe"""
    
    class Meta:
        model = TypingStatus
        fields = ['is_typing']
