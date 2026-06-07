import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import InAppNotification
from apps.chat.models import Conversation, Message

User = get_user_model()


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket pour les notifications en temps réel.
    
    Événements reçus:
    - Aucun (read-only pour le client)
    
    Événements envoyés:
    - notification_created: Nouvelle notification créée
    - unread_count_updated: Compteurs unread mis à jour
    - message_received: Nouveau message reçu (via chat)
    """
    
    async def connect(self):
        # Vérifier si l'utilisateur est authentifié
        if self.scope["user"].is_anonymous:
            await self.close()
            return
        
        self.user_id = self.scope["user"].id
        self.notification_group_name = f'notifications_{self.user_id}'
        
        # Rejoindre le groupe de notifications de l'utilisateur
        await self.channel_layer.group_add(
            self.notification_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Envoyer les compteurs actuels à la connexion
        await self.send_current_counts()
    
    async def disconnect(self, close_code):
        # Quitter le groupe de notifications
        await self.channel_layer.group_discard(
            self.notification_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        # Le client ne peut pas envoyer de messages (read-only)
        pass
    
    async def notification_created(self, event):
        """
        Envoyer une nouvelle notification au client.
        
        Payload:
        {
            'type': 'notification_created',
            'notification': {
                'id': str,
                'title': str,
                'body': str,
                'is_read': bool,
                'created_at': str (ISO format)
            }
        }
        """
        notification = event['notification']
        
        await self.send(text_data=json.dumps({
            'type': 'notification_created',
            'notification': notification
        }))
    
    async def unread_count_updated(self, event):
        """
        Envoyer les compteurs unread mis à jour.
        
        Payload:
        {
            'type': 'unread_count_updated',
            'unread_notifications': int,
            'unread_messages': int
        }
        """
        await self.send(text_data=json.dumps({
            'type': 'unread_count_updated',
            'unread_notifications': event.get('unread_notifications', 0),
            'unread_messages': event.get('unread_messages', 0)
        }))
    
    async def message_received(self, event):
        """
        Envoyer un événement de nouveau message reçu.
        
        Payload:
        {
            'type': 'message_received',
            'conversation_id': str,
            'message': {...}
        }
        """
        await self.send(text_data=json.dumps({
            'type': 'message_received',
            'conversation_id': event.get('conversation_id'),
            'message': event.get('message')
        }))
    
    @database_sync_to_async
    def get_unread_notification_count(self):
        """Récupérer le nombre de notifications non lues."""
        return InAppNotification.objects.filter(
            user_id=self.user_id,
            is_read=False
        ).count()
    
    @database_sync_to_async
    def get_unread_message_count(self):
        """Récupérer le nombre de messages non lus."""
        # Compter les conversations avec des messages non lus pour cet utilisateur
        from django.db.models import Q, Count
        
        unread_conversations = Conversation.objects.filter(
            Q(client_id=self.user_id) | Q(agent_id=self.user_id)
        ).annotate(
            unread_count=Count('messages', filter=Q(messages__is_read=False))
        ).filter(unread_count__gt=0)
        
        total_unread = sum(conv.unread_count for conv in unread_conversations)
        return total_unread
    
    async def send_current_counts(self):
        """Envoyer les compteurs actuels au client."""
        unread_notifications = await self.get_unread_notification_count()
        unread_messages = await self.get_unread_message_count()
        
        await self.send(text_data=json.dumps({
            'type': 'unread_count_updated',
            'unread_notifications': unread_notifications,
            'unread_messages': unread_messages
        }))
