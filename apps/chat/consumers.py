import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Message

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.mission_id = self.scope['url_route']['kwargs']['mission_id']
        self.room_group_name = f'chat_{self.mission_id}'

        # Rejoindre le groupe de la mission
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        content = data['message']
        sender = self.scope['user']

        # Sauvegarder en base de données
        await self.save_message(sender, content)

        # Envoyer le message au groupe
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': content,
                'sender': sender.username,
            }
        )

    async def chat_message(self, event):
        # Envoi effectif vers le WebSocket (Flutter)
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender']
        }))

    @database_sync_to_async
    def save_message(self, sender, content):
        from apps.missions.models import Mission
        mission = Mission.objects.get(id=self.mission_id)
        return Message.objects.create(mission=mission, sender=sender, content=content)