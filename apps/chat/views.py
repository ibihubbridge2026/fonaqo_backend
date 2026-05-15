from django.db import models
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Message
from .serializers import MessageSerializer, MessageCreateSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def message_list_view(request):
    """Liste des messages de l'utilisateur connecté."""
    user = request.user
    # Messages envoyés et reçus
    messages = Message.objects.filter(
        models.Q(sender=user) | models.Q(recipient=user)
    ).select_related('sender', 'recipient', 'mission').order_by('-timestamp')[:50]
    
    serializer = MessageSerializer(messages, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def message_create_view(request):
    """Créer un nouveau message."""
    serializer = MessageCreateSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        message = serializer.save()
        # Optionnel: envoyer une notification push au destinataire
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_message_read_view(request, message_id):
    """Marquer un message comme lu."""
    try:
        message = Message.objects.get(id=message_id, recipient=request.user)
        message.is_read = True
        message.save()
        return Response({'status': 'marked_read'}, status=status.HTTP_200_OK)
    except Message.DoesNotExist:
        return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)
