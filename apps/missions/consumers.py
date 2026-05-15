import json
import uuid
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.exceptions import ValidationError

from apps.core.choices import MissionStatus


class GpsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket `ws/gps/<mission_id>/` :
    - L'agent publie lat/lng (mission IN_PROGRESS uniquement).
    - Tous les membres reçoivent les mises à jour de statut (JSON type mission_status).
    """

    group_name: str
    mission_id: str
    is_agent: bool

    async def connect(self):
        self.mission_id = self.scope["url_route"]["kwargs"]["mission_id"]
        self.group_name = f"gps_{self.mission_id}"
        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        try:
            uuid.UUID(str(self.mission_id))
        except (ValueError, TypeError, AttributeError):
            await self.close(code=4400)
            return

        membership = await self._resolve_membership()
        if not membership["is_member"]:
            await self.close(code=4003)
            return

        self.is_agent = membership["is_agent"]

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        snap = await self._mission_snapshot()
        if snap:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "mission_status",
                        "status": snap["status"],
                        "destination_lat": snap["destination_lat"],
                        "destination_lng": snap["destination_lng"],
                    }
                )
            )

    async def disconnect(self, close_code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            data: dict[str, Any] = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"type": "error", "message": "JSON invalide."}))
            return

        msg_type = data.get("type", "location")

        if msg_type == "location":
            if not self.is_agent:
                await self.send(
                    text_data=json.dumps(
                        {"type": "error", "message": "Seul l'agent peut envoyer la position."}
                    )
                )
                return

            ok = await self._agent_can_stream_gps()
            if not ok:
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "error",
                            "message": "Envoi GPS refusé (mission non IN_PROGRESS).",
                        }
                    )
                )
                return

            lat = data.get("lat")
            lng = data.get("lng")
            if lat is None or lng is None:
                await self.send(
                    text_data=json.dumps({"type": "error", "message": "lat et lng requis."})
                )
                return

            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "gps.location.push",
                    "lat": float(lat),
                    "lng": float(lng),
                    "sender_channel": self.channel_name,
                },
            )
        else:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "message": "Type de message non pris en charge (utilisez l'API REST pour les statuts).",
                    }
                )
            )

    async def gps_location_push(self, event):
        """Diffuse la position aux autres membres (pas l'émetteur)."""
        if event.get("sender_channel") == self.channel_name:
            return
        await self.send(
            text_data=json.dumps(
                {
                    "type": "gps_update",
                    "lat": event["lat"],
                    "lng": event["lng"],
                }
            )
        )

    async def gps_client_push(self, event):
        """Message générique (ex. mission_status depuis le layer Django)."""
        await self.send(text_data=event["text"])

    @database_sync_to_async
    def _resolve_membership(self):
        from apps.missions.models import Mission

        try:
            mission = Mission.objects.filter(id=self.mission_id).select_related("agent", "client").first()
        except (ValueError, ValidationError):
            return {"is_member": False, "is_agent": False}

        if mission is None:
            return {"is_member": False, "is_agent": False}

        user = self.scope["user"]
        is_member = user in (mission.client, mission.agent)
        is_agent = mission.agent_id == user.id
        return {"is_member": is_member, "is_agent": is_agent}

    @database_sync_to_async
    def _agent_can_stream_gps(self):
        from apps.missions.models import Mission

        mission = Mission.objects.filter(id=self.mission_id).only("status", "agent_id").first()
        if mission is None:
            return False
        if mission.agent_id != self.scope["user"].id:
            return False
        return mission.status == MissionStatus.IN_PROGRESS

    @database_sync_to_async
    def _mission_snapshot(self):
        from apps.missions.models import Mission

        m = Mission.objects.filter(id=self.mission_id).only("status", "location").first()
        if m is None or m.location is None:
            return None
        return {
            "status": m.status,
            "destination_lat": m.location.y,
            "destination_lng": m.location.x,
        }
