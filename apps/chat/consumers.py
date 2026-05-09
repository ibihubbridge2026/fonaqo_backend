import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Message

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.mission_id = self.scope['url_route']['kwargs']['mission_id']
        self.room_group_name = f'chat_{self.mission_id}'
        user = self.scope['user']

        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        # Verification d'acces stricte (client/agent de la mission uniquement)
        if not await self.is_member_of_mission(user):
            await self.close(code=4003)
            return

        if not await self._mission_exists():
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    @database_sync_to_async
    def is_member_of_mission(self, user):
        from apps.missions.models import Mission
        try:
            mission = Mission.objects.get(id=self.mission_id)
            return user == mission.client or user == mission.agent
        except Mission.DoesNotExist:
            return False    

    @database_sync_to_async
    def _mission_exists(self):
        from apps.missions.models import Mission
        return Mission.objects.filter(id=self.mission_id).exists()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        event_type = data.get('type', 'message')  # On récupère le type d'événement
        sender = self.scope['user']

        if event_type == 'message':
            content = data.get('message')
            if not content:
                return
            # 1. Sauvegarder dans PostgreSQL
            await self.save_message(sender, content)
            
            # 2. Diffuser le message à la "room"
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': content,
                    'sender': sender.username,
                }
            )

        elif event_type == 'typing':
            # On ne sauvegarde pas en base, on diffuse juste l'info en direct
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_typing',
                    'sender': sender.username,
                    'is_typing': data.get('is_typing', True)
                }
            )

    async def chat_message(self, event):
        # Envoi effectif vers le WebSocket (Flutter)
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender']
        }))

    async def user_typing(self, event):
        """Transmet l'état 'en train d'écrire' à l'autre utilisateur"""
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'sender': event['sender'],
            'is_typing': event['is_typing']
        }))
        
    @database_sync_to_async
    def save_message(self, sender, content):
        from apps.missions.models import Mission
        mission = Mission.objects.get(id=self.mission_id)
        return Message.objects.create(mission=mission, sender=sender, content=content)