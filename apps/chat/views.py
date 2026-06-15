import uuid

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import models
from .models import Conversation, Message, TypingStatus, ChatAttachment, UserPresence
from .serializers import (
    ConversationSerializer, ConversationCreateSerializer,
    MessageSerializer, MessageCreateSerializer, MessageMarkReadSerializer,
    TypingStatusSerializer, TypingStatusUpdateSerializer,
    ChatAttachmentSerializer, UserPresenceSerializer,
)


def send_system_message(mission, text: str):
    """
    Crée un message système dans la conversation liée à une mission.
    Appelé depuis les vues mission lors des changements de statut.
    Retourne le Message créé ou None si pas de conversation.
    """
    conversation = Conversation.objects.filter(mission=mission).first()
    if conversation is None:
        return None
    msg = Message.objects.create(
        conversation=conversation,
        sender=mission.client,  # sender arbitraire pour les messages système
        message_type='system',
        content=text,
        delivery_status=Message.DeliveryStatus.SENT,
    )
    return msg


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

    def list(self, request, *args, **kwargs):
        """Listing générique obsolète — utiliser my_conversations/."""
        return Response(
            {
                'detail': 'Endpoint obsolète. '
                'Utilisez GET /api/v1/chat/conversations/my_conversations/',
            },
            status=status.HTTP_410_GONE,
        )
    
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
            context={'request': request, 'conversation': conversation},
        )
        
        if serializer.is_valid():
            # Déduplication REST : si client_message_id déjà reçu, retourner l'existant
            client_mid = serializer.validated_data.get('client_message_id')
            if client_mid:
                existing = Message.objects.filter(client_message_id=client_mid).first()
                if existing:
                    return Response(
                        MessageSerializer(existing, context={'request': request}).data,
                        status=status.HTTP_200_OK,
                    )

            message = serializer.save(
                conversation=conversation,
                sender=request.user,
                delivery_status=Message.DeliveryStatus.SENT,
            )
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
            
            # Compter avant l'update (le queryset est consommé ensuite)
            marked_count = messages_to_mark.count()
            messages_to_mark.update(is_read=True, read_at=timezone.now())
            
            # Mettre à jour uniquement le champ last_read de l'utilisateur courant
            now = timezone.now()
            if conversation.client == request.user:
                conversation.client_last_read = now
                conversation.save(update_fields=['client_last_read'])
            else:
                conversation.agent_last_read = now
                conversation.save(update_fields=['agent_last_read'])
            
            return Response({
                'marked_count': marked_count,
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
        # Cas agent=None (mission PENDING): unique_together avec NULL ne fonctionne pas
        # en PostgreSQL (NULL != NULL), donc on filtre manuellement pour éviter les doublons.
        if mission.agent is not None:
            conversation, created = Conversation.objects.get_or_create(
                mission=mission,
                client=mission.client,
                agent=mission.agent,
            )
        else:
            conversation = Conversation.objects.filter(
                mission=mission,
                client=mission.client,
            ).first()
            if conversation is None:
                conversation = Conversation.objects.create(
                    mission=mission,
                    client=mission.client,
                    agent=None,
                )
                created = True
            else:
                created = False
        
        serializer = ConversationSerializer(conversation, context={'request': request})
        
        return Response(
            serializer.data,
            status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['get'])
    def messages_after(self, request, pk=None):
        """
        GET /conversations/{id}/messages_after/?last_message_id=<id>
        Retourne les messages postérieurs à last_message_id (rattrapage reconnect).
        """
        conversation = self.get_object()
        if not (conversation.client == request.user or conversation.agent == request.user):
            return Response({'error': 'Permission refusée'}, status=status.HTTP_403_FORBIDDEN)

        qs = conversation.messages.order_by('created_at')
        last_id = request.query_params.get('last_message_id')
        if last_id:
            try:
                ref = Message.objects.get(id=int(last_id))
                qs = qs.filter(created_at__gt=ref.created_at)
            except (Message.DoesNotExist, ValueError):
                pass
        serializer = MessageSerializer(qs[:200], many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def send_attachment(self, request, pk=None):
        """
        Upload une pièce jointe dans un message existant ou nouveau.
        POST body : file, attachment_type, [message_id]

        Validation :
        - Taille max 10MB
        - MIME autorisés : pdf, jpg, jpeg, png, aac, m4a
        - MIME bloqués : exe, apk, bat, js, php
        """
        conversation = self.get_object()
        if not (conversation.client == request.user or conversation.agent == request.user):
            return Response({'error': 'Permission refusée'}, status=status.HTTP_403_FORBIDDEN)

        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'error': 'Fichier requis'}, status=status.HTTP_400_BAD_REQUEST)

        # Validation taille (10MB max)
        MAX_FILE_SIZE = 10 * 1024 * 1024
        if uploaded.size > MAX_FILE_SIZE:
            return Response(
                {'error': 'Fichier trop volumineux (max 10MB)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validation MIME type
        ALLOWED_MIME_TYPES = {
            'application/pdf',
            'image/jpeg',
            'image/jpg',
            'image/png',
            'audio/aac',
            'audio/x-m4a',
            'audio/mp4',
        }
        BLOCKED_EXTENSIONS = {'.exe', '.apk', '.bat', '.js', '.php', '.sh', '.cmd'}

        file_name = uploaded.name.lower()
        if any(file_name.endswith(ext) for ext in BLOCKED_EXTENSIONS):
            return Response(
                {'error': 'Type de fichier non autorisé'},
                status=status.HTTP_400_BAD_REQUEST
            )

        mime_type = uploaded.content_type
        if mime_type not in ALLOWED_MIME_TYPES:
            return Response(
                {'error': f'Type MIME non autorisé: {mime_type}. Types autorisés: pdf, jpg, png, aac, m4a'},
                status=status.HTTP_400_BAD_REQUEST
            )

        attachment_type = request.data.get('attachment_type', 'file')
        message_id = request.data.get('message_id')

        if message_id:
            try:
                message = Message.objects.get(id=message_id, conversation=conversation)
            except Message.DoesNotExist:
                return Response({'error': 'Message introuvable'}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Créer un message porteur
            client_mid = request.data.get('client_message_id')
            if client_mid:
                existing = Message.objects.filter(client_message_id=client_mid).first()
                if existing:
                    message = existing
                else:
                    message = Message.objects.create(
                        conversation=conversation,
                        sender=request.user,
                        message_type='file',
                        client_message_id=uuid.UUID(client_mid),
                        delivery_status=Message.DeliveryStatus.SENT,
                    )
            else:
                message = Message.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    message_type=attachment_type if attachment_type in ('image', 'voice', 'file') else 'file',
                    delivery_status=Message.DeliveryStatus.SENT,
                )

        attachment = ChatAttachment.objects.create(
            message=message,
            attachment_type=attachment_type,
            file=uploaded,
            original_filename=uploaded.name,
            file_size=uploaded.size,
            mime_type=uploaded.content_type or '',
        )
        return Response(
            ChatAttachmentSerializer(attachment, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'])
    def my_conversations(self, request):
        """Lister les conversations de l'utilisateur"""
        conversations = self.get_queryset().filter(is_archived=False)
        serializer = self.get_serializer(conversations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def presence(self, request, pk=None):
        """Récupère la présence des participants d'une conversation."""
        conversation = self.get_object()
        participants = [p for p in [conversation.client, conversation.agent] if p]
        presences = []
        for p in participants:
            pres, _ = UserPresence.objects.get_or_create(user=p)
            presences.append(pres)
        return Response(UserPresenceSerializer(presences, many=True).data)


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


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def heartbeat(request):
    """
    Endpoint heartbeat pour mettre à jour last_seen.
    Le client Flutter doit appeler cette endpoint toutes les 30-60 secondes
    pour maintenir la présence active et détecter les déconnexions brutales.
    """
    presence, _ = UserPresence.objects.get_or_create(user=request.user)
    presence.mark_online()
    return Response({'status': 'ok', 'last_seen': presence.last_seen.isoformat()})
