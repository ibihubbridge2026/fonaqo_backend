import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

class GpsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.mission_id = self.scope['url_route']['kwargs']['mission_id']
        self.group_name = f'gps_{self.mission_id}'
        self.user = self.scope["user"]

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.is_member, self.is_agent = await self._resolve_membership()
        if not self.is_member:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Réception de la position envoyée par l'AGENT"""
        if not self.is_agent:
            await self.send(text_data=json.dumps({"error": "Only mission agent can publish GPS."}))
            return

        data = json.loads(text_data)
        
        # On extrait la latitude et longitude
        lat = data.get('lat')
        lng = data.get('lng')
        if lat is None or lng is None:
            await self.send(text_data=json.dumps({"error": "lat/lng are required"}))
            return

        # On diffuse l'info au groupe (au CLIENT)
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'gps_location_update',
                'lat': lat,
                'lng': lng,
            }
        )

    async def gps_location_update(self, event):
        """Envoi effectif au téléphone du CLIENT"""
        await self.send(text_data=json.dumps({
            'type': 'gps_update',
            'lat': event['lat'],
            'lng': event['lng']
        }))

    @database_sync_to_async
    def _resolve_membership(self):
        from apps.missions.models import Mission

        mission = Mission.objects.filter(id=self.mission_id).select_related("agent", "client").first()
        if mission is None:
            return False, False

        is_member = self.user in (mission.client, mission.agent)
        is_agent = mission.agent_id == self.user.id
        return is_member, is_agent