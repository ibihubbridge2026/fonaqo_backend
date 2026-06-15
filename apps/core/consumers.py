import json
import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)
User = get_user_model()


def _user_from_token(token: str):
    if not token:
        return None
    try:
        access = AccessToken(token)
        user_id = access.get('user_id')
        if not user_id:
            return None
        return User.objects.filter(pk=user_id, is_active=True).first()
    except Exception:
        return None


@database_sync_to_async
def _get_mission_participants(mission_id: str):
    from apps.missions.models import Mission

    try:
        mission = Mission.objects.select_related('client', 'agent').get(pk=mission_id)
    except Mission.DoesNotExist:
        return None, None, None
    return mission, mission.client_id, mission.agent_id


class GpsConsumer(AsyncWebsocketConsumer):
    """Diffusion position agent → client pour une mission."""

    async def connect(self):
        self.mission_id = self.scope['url_route']['kwargs']['mission_id']
        self.group_name = f'gps_{self.mission_id}'

        query = parse_qs(self.scope.get('query_string', b'').decode())
        token = (query.get('token') or [''])[0]
        user = await database_sync_to_async(_user_from_token)(token)
        if user is None:
            await self.close(code=4401)
            return

        mission, client_id, agent_id = await _get_mission_participants(self.mission_id)
        if mission is None:
            await self.close(code=4404)
            return

        if user.id not in {client_id, agent_id}:
            await self.close(code=4403)
            return

        self.user = user
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({'type': 'connected', 'mission_id': self.mission_id}))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = payload.get('type')
        if msg_type == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))
            return

        if msg_type == 'location':
            lat = payload.get('lat')
            lng = payload.get('lng')
            if lat is None or lng is None:
                return
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'gps.broadcast',
                    'lat': lat,
                    'lng': lng,
                    'sender_id': self.user.id,
                },
            )

    async def gps_broadcast(self, event):
        await self.send(
            text_data=json.dumps({
                'type': 'gps_update',
                'lat': event['lat'],
                'lng': event['lng'],
                'sender_id': event.get('sender_id'),
            }),
        )


class TimelineConsumer(AsyncWebsocketConsumer):
    """Événements timeline mission (étapes agent)."""

    async def connect(self):
        self.mission_id = self.scope['url_route']['kwargs']['mission_id']
        self.group_name = f'timeline_{self.mission_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return
        await self.channel_layer.group_send(
            self.group_name,
            {'type': 'timeline.broadcast', 'payload': payload},
        )

    async def timeline_broadcast(self, event):
        await self.send(text_data=json.dumps(event['payload']))
