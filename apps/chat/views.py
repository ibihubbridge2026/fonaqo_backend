from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import models
from .models import Conversation, Message, TypingStatus
from .serializers import (
    ConversationSerializer, ConversationCreateSerializer,
    MessageSerializer, MessageCreateSerializer, MessageMarkReadSerializer,
    TypingStatusSerializer, TypingStatusUpdateSerializer
)


class IsConversationParticipant(permissions.BasePermission):
    """Permission pour vérifier si l'utilisateur participe à la conversation"""
    
    def has_object_permission(self, request, view, obj):
        return obj.client == request.user or obj.agent == request.user


class ConversationViewSet(viewsets.ModelViewSet):
    """ViewSet pour les conversations"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        return Conversation.objects.filter(
            models.Q(client=user) | models.Q(agent=user)
        ).distinct()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ConversationCreateSerializer
        return ConversationSerializer
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """Lister les messages d'une conversation"""
        conversation = self.get_object()
        
        # Vérifier que l'utilisateur participe à la conversation
        if not (conversation.client == request.user or conversation.agent == request.user):
            return Response(
                {'error': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        messages = conversation.messages.all().order_by('created_at')
        serializer = MessageSerializer(messages, many=True, context={'request': request})
        
        # Marquer les messages comme lus
        if conversation.client == request.user:
            conversation.client_last_read = timezone.now()
        else:
            conversation.agent_last_read = timezone.now()
        conversation.save(update_fields=['client_last_read', 'agent_last_read'])
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """Envoyer un message dans une conversation"""
        conversation = self.get_object()
        
        # Vérifier que l'utilisateur participe à la conversation
        if not (conversation.client == request.user or conversation.agent == request.user):
            return Response(
                {'error': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = MessageCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            message = serializer.save(
                conversation=conversation,
                sender=request.user
            )
            
            # Mettre à jour le last_message_at de la conversation
            conversation.last_message_at = message.created_at
            conversation.save(update_fields=['last_message_at'])
            
            return Response(
                MessageSerializer(message, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Marquer des messages comme lus"""
        conversation = self.get_object()
        
        # Vérifier que l'utilisateur participe à la conversation
        if not (conversation.client == request.user or conversation.agent == request.user):
            return Response(
                {'error': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = MessageMarkReadSerializer(data=request.data)
        if serializer.is_valid():
            message_ids = serializer.validated_data.get('message_ids')
            mark_all = serializer.validated_data.get('mark_all', False)
            
            if mark_all:
                # Marquer tous les messages non lus
                if conversation.client == request.user:
                    messages_to_mark = conversation.messages.filter(sender=conversation.agent, is_read=False)
                else:
                    messages_to_mark = conversation.messages.filter(sender=conversation.client, is_read=False)
            else:
                # Marquer des messages spécifiques
                messages_to_mark = conversation.messages.filter(id__in=message_ids, is_read=False)
            
            # Marquer les messages comme lus
            messages_to_mark.update(is_read=True, read_at=timezone.now())
            
            # Mettre à jour le last_read de la conversation
            if conversation.client == request.user:
                conversation.client_last_read = timezone.now()
            else:
                conversation.agent_last_read = timezone.now()
            conversation.save(update_fields=['client_last_read', 'agent_last_read'])
            
            return Response({
                'marked_count': messages_to_mark.count(),
                'message': 'Messages marqués comme lus'
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def typing_status(self, request, pk=None):
        """Mettre à jour le statut \"en train d'écrire\""""
        conversation = self.get_object()
        
        # Vérifier que l'utilisateur participe à la conversation
        if not (conversation.client == request.user or conversation.agent == request.user):
            return Response(
                {'error': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = TypingStatusUpdateSerializer(data=request.data)
        if serializer.is_valid():
            typing_status, created = TypingStatus.objects.update_or_create(
                conversation=conversation,
                user=request.user,
                defaults=serializer.validated_data
            )
            
            return Response(
                TypingStatusSerializer(typing_status).data
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archiver une conversation"""
        conversation = self.get_object()
        conversation.is_archived = True
        conversation.save(update_fields=['is_archived'])
        
        return Response({
            'message': 'Conversation archivée',
            'is_archived': True
        })
    
    @action(detail=False, methods=['post'])
    def get_or_create(self, request):
        """
        Crée ou récupère une conversation pour une mission
        Payload: {"mission_id": "<uuid>"}
        """
        mission_id = request.data.get('mission_id')
        
        if not mission_id:
            return Response(
                {'error': 'mission_id est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Vérifier que la mission existe
        from apps.missions.models import Mission
        try:
            mission = Mission.objects.get(pk=mission_id)
        except Mission.DoesNotExist:
            return Response(
                {'error': 'Mission non trouvée'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Vérifier que l'utilisateur participe à la mission
        if mission.client != request.user and mission.agent != request.user:
            return Response(
                {'error': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Créer ou récupérer la conversation
        conversation, created = Conversation.objects.get_or_create(
            mission=mission,
            client=mission.client,
            agent=mission.agent,
            defaults={
                'client': mission.client,
                'agent': mission.agent,
                'mission': mission,
            }
        )
        
        serializer = ConversationSerializer(conversation, context={'request': request})
        
        return Response(
            serializer.data,
            status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED
        )
    
    @action(detail=False, methods=['get'])
    def my_conversations(self, request):
        """Lister les conversations de l'utilisateur"""
        conversations = self.get_queryset().filter(is_archived=False)
        serializer = self.get_serializer(conversations, many=True)
        return Response(serializer.data)


class MessageViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les messages (lecture seule)"""
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(
            conversation__client=user
        ).union(
            Message.objects.filter(conversation__agent=user)
        ).order_by('-created_at')


class TypingStatusViewSet(viewsets.ModelViewSet):
    """ViewSet pour les statuts de frappe"""
    serializer_class = TypingStatusSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        return TypingStatus.objects.filter(
            conversation__client=user
        ).union(
            TypingStatus.objects.filter(conversation__agent=user)
        )
