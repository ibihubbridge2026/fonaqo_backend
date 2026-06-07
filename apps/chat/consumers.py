import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Conversation, Message

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.mission_id = self.scope['url_route']['kwargs']['mission_id']
        self.conversation_group_name = f'chat_{self.mission_id}'
        
        # Vérifier si l'utilisateur est authentifié
        if self.scope["user"].is_anonymous:
            await self.close()
            return
        
        # Résoudre la conversation depuis la mission
        self.conversation = await self.get_or_create_conversation()
        if self.conversation is None:
            await self.close()
            return

        # Vérifier si l'utilisateur participe à la conversation
        if not await self.is_participant():
            await self.close()
            return
        
        # Rejoindre le groupe de conversation
        await self.channel_layer.group_add(
            self.conversation_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Quitter le groupe de conversation
        await self.channel_layer.group_discard(
            self.conversation_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'text')
            content = data.get('content', '')
            
            # Créer et sauvegarder le message
            message = await self.create_message(message_type, content)
            
            # Envoyer le message au groupe
            await self.channel_layer.group_send(
                self.conversation_group_name,
                {
                    'type': 'chat_message',
                    'message': {
                        'id': str(message.id),
                        'content': message.content,
                        'message_type': message.message_type,
                        'sender': message.sender.username if message.sender else 'Unknown',
                        'sender_id': str(message.sender.id) if message.sender else None,
                        'timestamp': message.created_at.isoformat(),
                        'media_url': message.media_file.url if message.media_file else None,
                        'audio_url': message.audio_file.url if message.audio_file else None,
                        'audio_duration': message.audio_duration,
                    }
                }
            )
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))
    
    async def chat_message(self, event):
        message = event['message']
        
        # Envoyer le message au WebSocket
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': message
        }))
    
    @database_sync_to_async
    def get_or_create_conversation(self):
        from apps.missions.models import Mission
        try:
            mission = Mission.objects.get(pk=self.mission_id)
            conversation, _ = Conversation.objects.get_or_create(
                mission=mission,
                defaults={
                    'client': mission.client,
                    'agent': mission.agent,
                }
            )
            return conversation
        except Mission.DoesNotExist:
            return None

    @database_sync_to_async
    def is_participant(self):
        user = self.scope["user"]
        conv = self.conversation
        return conv.client == user or conv.agent == user
    
    @database_sync_to_async
    def create_message(self, message_type, content):
        try:
            sender = self.scope["user"]
            message = Message.objects.create(
                conversation=self.conversation,
                sender=sender,
                content=content,
                message_type=message_type
            )
            return message
        except Exception:
            return None
