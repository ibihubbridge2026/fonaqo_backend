import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Mission, MissionProof, MissionTimelineEvent

User = get_user_model()

class MissionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.mission_id = self.scope['url_route']['kwargs']['mission_id']
        self.mission_group_name = f'mission_{self.mission_id}'
        
        # Vérifier si l'utilisateur est authentifié
        if self.scope["user"].is_anonymous:
            await self.close()
            return
        
        # Vérifier si l'utilisateur participe à la mission
        if not await self.is_participant():
            await self.close()
            return
        
        # Rejoindre le groupe de mission
        await self.channel_layer.group_add(
            self.mission_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Quitter le groupe de mission
        await self.channel_layer.group_discard(
            self.mission_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'status_update')
            
            # Gérer différents types de messages
            if message_type == 'status_update':
                new_status = data.get('status')
                await self.update_mission_status(new_status)
            elif message_type == 'location' or message_type == 'location_update':
                lat = data.get('lat') or data.get('latitude')
                lng = data.get('lng') or data.get('longitude')
                if lat and lng:
                    await self.update_agent_location(lat, lng)
                    # Diffuser la position GPS au groupe (pour le client)
                    await self.channel_layer.group_send(
                        self.mission_group_name,
                        {
                            'type': 'gps_broadcast',
                            'message': {
                                'type': 'gps_update',
                                'lat': lat,
                                'lng': lng,
                                'mission_id': self.mission_id,
                                'timestamp': self.get_current_timestamp()
                            }
                        }
                    )
            elif message_type == 'proof_upload':
                proof_data = data.get('proof')
                await self.handle_proof_upload(proof_data)
            
            # Envoyer la mise à jour au groupe pour les autres types
            if message_type not in ['location', 'location_update']:
                await self.channel_layer.group_send(
                    self.mission_group_name,
                    {
                        'type': 'mission_update',
                        'message': {
                            'type': message_type,
                            'mission_id': self.mission_id,
                            'data': data,
                            'timestamp': self.get_current_timestamp()
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
    
    async def mission_update(self, event):
        message = event['message']
        
        # Envoyer la mise à jour au WebSocket
        await self.send(text_data=json.dumps({
            'type': 'update',
            'message': message
        }))
    
    async def gps_broadcast(self, event):
        """Diffuse les mises à jour GPS à tous les clients connectés"""
        message = event['message']
        await self.send(text_data=json.dumps(message))
    
    @database_sync_to_async
    def is_participant(self):
        try:
            mission = Mission.objects.get(id=self.mission_id)
            user = self.scope["user"]
            return mission.client == user or mission.agent == user
        except Mission.DoesNotExist:
            return False
    
    VALID_STATUSES = {'PENDING', 'ACCEPTED', 'ON_THE_WAY', 'ARRIVED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'DISPUTED'}

    @database_sync_to_async
    def update_mission_status(self, new_status):
        try:
            mission = Mission.objects.get(id=self.mission_id)
            if new_status in self.VALID_STATUSES:
                mission.status = new_status
                mission.save(update_fields=['status', 'updated_at'])
                MissionTimelineEvent.objects.create(
                    mission=mission,
                    event_type=new_status.lower(),
                    performed_by=self.scope["user"],
                    notes=f"Statut mis à jour via WebSocket: {new_status}"
                )
                return True
        except Mission.DoesNotExist:
            pass
        return False

    @database_sync_to_async
    def update_agent_location(self, lat, lng):
        """Met à jour la position GPS de l'agent et la diffuse au groupe."""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = self.scope["user"]
            mission = Mission.objects.get(id=self.mission_id)
            if mission.agent == user:
                User.objects.filter(pk=user.pk).update(latitude=lat, longitude=lng)
                return True
        except Mission.DoesNotExist:
            pass
        return False
    
    @database_sync_to_async
    def handle_proof_upload(self, proof_data):
        try:
            mission = Mission.objects.get(id=self.mission_id)
            if mission.agent == self.scope["user"]:
                # Gérer l'upload de preuves
                pass
        except Mission.DoesNotExist:
            pass
    
    def get_current_timestamp(self):
        from django.utils import timezone
        return timezone.now().isoformat()
