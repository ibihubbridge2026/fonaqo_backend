from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .serializers import FCMDeviceSerializer, InAppNotificationSerializer
from .models import InAppNotification


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
    return Response({'status': 'marked_read'}, status=status.HTTP_200_OK)