from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .serializers import FCMDeviceSerializer, InAppNotificationSerializer
from .models import InAppNotification


def send_notification_event(user_id, event_type, data):
    """
    Envoyer un événement WebSocket à un utilisateur spécifique.
    
    Args:
        user_id: ID de l'utilisateur cible
        event_type: Type d'événement ('notification_created', 'unread_count_updated', 'message_received')
        data: Données de l'événement (dict)
    """
    channel_layer = get_channel_layer()
    group_name = f'notifications_{user_id}'
    
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': event_type,
            **data
        }
    )


class RegisterDeviceView(generics.CreateAPIView):
    serializer_class = FCMDeviceSerializer
    permission_classes = [permissions.IsAuthenticated]


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def notification_list_view(request):
    """Liste des notifications de l'utilisateur connecté."""
    notifications = InAppNotification.objects.filter(user=request.user)[:50]
    serializer = InAppNotificationSerializer(notifications, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_notification_read_view(request, notification_id):
    """Marquer une notification comme lue."""
    notification = get_object_or_404(InAppNotification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    
    # Envoyer événement WebSocket pour mettre à jour les compteurs
    from apps.chat.models import Conversation, Message
    from django.db.models import Q, Count
    
    unread_notifications = InAppNotification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    unread_conversations = Conversation.objects.filter(
        Q(client=request.user) | Q(agent=request.user)
    ).annotate(
        unread_count=Count('messages', filter=Q(messages__is_read=False))
    ).filter(unread_count__gt=0)
    
    unread_messages = sum(conv.unread_count for conv in unread_conversations)
    
    send_notification_event(
        request.user.id,
        'unread_count_updated',
        {
            'unread_notifications': unread_notifications,
            'unread_messages': unread_messages
        }
    )
    
    return Response({'status': 'marked_read'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_all_notifications_read_view(request):
    """Marquer toutes les notifications de l'utilisateur comme lues."""
    count = InAppNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    
    # Envoyer événement WebSocket pour mettre à jour les compteurs
    from apps.chat.models import Conversation, Message
    from django.db.models import Q, Count
    
    unread_conversations = Conversation.objects.filter(
        Q(client=request.user) | Q(agent=request.user)
    ).annotate(
        unread_count=Count('messages', filter=Q(messages__is_read=False))
    ).filter(unread_count__gt=0)
    
    unread_messages = sum(conv.unread_count for conv in unread_conversations)
    
    send_notification_event(
        request.user.id,
        'unread_count_updated',
        {
            'unread_notifications': 0,
            'unread_messages': unread_messages
        }
    )
    
    return Response({
        'status': 'all_marked_read',
        'count': count
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def unread_count_view(request):
    """Nombre de notifications non lues de l'utilisateur connecté."""
    count = InAppNotification.objects.filter(user=request.user, is_read=False).count()
    return Response({'unread_count': count}, status=status.HTTP_200_OK)