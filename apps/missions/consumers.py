import json
from channels.generic.websocket import AsyncWebsocketConsumer

class GpsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.mission_id = self.scope['url_route']['kwargs']['mission_id']
        self.group_name = f'gps_{self.mission_id}'

        # Tout le monde peut écouter (ou ajouter une sécurité client/agent ici)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Réception de la position envoyée par l'AGENT"""
        data = json.loads(text_data)
        
        # On extrait la latitude et longitude
        lat = data.get('lat')
        lng = data.get('lng')

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