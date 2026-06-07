import logging

from fcm_django.models import FCMDevice
from firebase_admin import messaging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import InAppNotification

logger = logging.getLogger(__name__)


class NotificationService:
    @staticmethod
    def send_to_user(user, title, body, data=None):
        """
        Envoie une notification Push réelle via Firebase FCM.
        Utilise les devices enregistrés via FCMDevice (fcm-django).
        """
        devices = FCMDevice.objects.filter(user=user, active=True)

        if not devices.exists():
            logger.info(
                "Pas de device FCM pour %s. Notification ignorée: %s",
                user.username, title
            )
            return False

        try:
            result = devices.send_message(
                messaging.Message(
                    notification=messaging.Notification(
                        title=title,
                        body=body,
                    ),
                    data=data or {},
                )
            )
            logger.info("Notification envoyée à %s: %s", user.username, title)
            return True
        except Exception as e:
            logger.error("Erreur lors de l'envoi FCM à %s: %s", user.username, e)
            return False
    
    @staticmethod
    def create_in_app_notification(user, title, body, data=None):
        """
        Crée une notification in-app et envoie l'événement WebSocket.
        
        Args:
            user: Utilisateur cible
            title: Titre de la notification
            body: Corps de la notification
            data: Données additionnelles (dict)
        
        Returns:
            InAppNotification: La notification créée
        """
        notification = InAppNotification.objects.create(
            user=user,
            title=title,
            body=body or ''
        )
        
        # Envoyer événement WebSocket
        channel_layer = get_channel_layer()
        group_name = f'notifications_{user.id}'
        
        notification_data = {
            'id': str(notification.id),
            'title': notification.title,
            'body': notification.body,
            'is_read': notification.is_read,
            'created_at': notification.created_at.isoformat()
        }
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification_created',
                'notification': notification_data
            }
        )
        
        # Envoyer également la mise à jour des compteurs
        from apps.chat.models import Conversation
        from django.db.models import Q, Count
        
        unread_notifications = InAppNotification.objects.filter(
            user=user,
            is_read=False
        ).count()
        
        unread_conversations = Conversation.objects.filter(
            Q(client=user) | Q(agent=user)
        ).annotate(
            unread_count=Count('messages', filter=Q(messages__is_read=False))
        ).filter(unread_count__gt=0)
        
        unread_messages = sum(conv.unread_count for conv in unread_conversations)
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'unread_count_updated',
                'unread_notifications': unread_notifications,
                'unread_messages': unread_messages
            }
        )
        
        logger.info("Notification in-app créée pour %s: %s", user.username, title)
        return notification