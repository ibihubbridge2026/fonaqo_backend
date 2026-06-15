"""
Consumer WebSocket chat — production grade.

Fonctionnalités :
  - Authentification JWT via token en query string
  - Déduplication côté serveur (client_message_id unique)
  - ACK serveur après création du message
  - Statuts SENT → DELIVERED → READ
  - Rattrapage au reconnect (messages since last_message_id)
  - Présence utilisateur (online / last_seen)
  - Typing indicator avec expiration 5 secondes
  - Messages système automatiques (envoyés depuis la vue mission)
"""
import json
import uuid
from datetime import timedelta

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import Conversation, Message, TypingStatus, UserPresence

User = get_user_model()

TYPING_EXPIRY_SECONDS = 5


def _message_to_dict(msg: Message, request=None) -> dict:
    """Sérialise un Message en dict JSON-safe (compatible Flutter ChatMessageV2)."""
    # Mapping delivery_status backend → status Flutter
    _status_map = {
        'pending':   'sending',
        'sent':      'sent',
        'delivered': 'delivered',
        'read':      'read',
    }
    return {
        'id':                str(msg.id),
        'client_message_id': str(msg.client_message_id) if msg.client_message_id else None,
        'conversation_id':   str(msg.conversation_id),
        'content':           msg.content,
        # Alias Flutter-compat
        'type':              msg.message_type,
        'message_type':      msg.message_type,
        'sender':            msg.sender.username if msg.sender else None,
        'sender_id':         str(msg.sender.id) if msg.sender else None,
        'sender_name':       msg.sender.get_full_name() or msg.sender.username if msg.sender else None,
        # Alias Flutter-compat
        'status':            _status_map.get(msg.delivery_status, 'sent'),
        'delivery_status':   msg.delivery_status,
        'is_read':           msg.is_read,
        'read_at':           msg.read_at.isoformat() if msg.read_at else None,
        'delivered_at':      msg.delivered_at.isoformat() if msg.delivered_at else None,
        'timestamp':         msg.created_at.isoformat(),
        'media_url':         msg.media_file.url if msg.media_file else None,
        'audio_url':         msg.audio_file.url if msg.audio_file else None,
        'audio_duration':    msg.audio_duration,
        'duration':          msg.audio_duration,
        'is_deleted':        msg.is_deleted,
        'proposed_price':    str(msg.proposed_price) if msg.proposed_price is not None else None,
        'negotiation_status': msg.negotiation_status,
    }


class ChatConsumer(AsyncWebsocketConsumer):

    # ──────────────────────────────────────────────────────────────────────────
    # Connexion / déconnexion
    # ──────────────────────────────────────────────────────────────────────────

    async def connect(self):
        self.mission_id = self.scope['url_route']['kwargs']['mission_id']
        self.group_name = f'chat_{self.mission_id}'
        self.user = self.scope.get('user')

        if not self.user or self.user.is_anonymous:
            await self.close(code=4001)
            return

        self.conversation = await self.get_or_create_conversation()
        if self.conversation is None:
            await self.close(code=4004)
            return

        if not await self.is_participant():
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Marquer l'utilisateur en ligne
        await self.set_presence(online=True)

        # Diffuser la présence au groupe
        await self.channel_layer.group_send(self.group_name, {
            'type': 'presence_update',
            'user_id': str(self.user.id),
            'username': self.user.username,
            'is_online': True,
            'last_seen': timezone.now().isoformat(),
        })

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self.set_presence(online=False)

        if hasattr(self, 'group_name') and hasattr(self, 'user'):
            await self.channel_layer.group_send(self.group_name, {
                'type': 'presence_update',
                'user_id': str(self.user.id),
                'username': self.user.username,
                'is_online': False,
                'last_seen': timezone.now().isoformat(),
            })

    # ──────────────────────────────────────────────────────────────────────────
    # Dispatcher principal
    # ──────────────────────────────────────────────────────────────────────────

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error('invalid_json', 'Format JSON invalide')
            return

        event_type = data.get('type', 'message')

        if event_type == 'message':
            await self._handle_message(data)
        elif event_type == 'typing_start':
            await self._handle_typing(data, is_typing=True)
        elif event_type == 'typing_stop':
            await self._handle_typing(data, is_typing=False)
        elif event_type == 'mark_read':
            await self._handle_mark_read(data)
        elif event_type == 'catchup':
            await self._handle_catchup(data)
        elif event_type == 'heartbeat':
            await self.send(text_data=json.dumps({'type': 'heartbeat_ack'}))
        else:
            await self._send_error('unknown_type', f'Type inconnu : {event_type}')

    # ──────────────────────────────────────────────────────────────────────────
    # Handlers
    # ──────────────────────────────────────────────────────────────────────────

    async def _handle_message(self, data: dict):
        client_msg_id = data.get('client_message_id')
        content = data.get('content', '').strip()
        message_type = data.get('message_type', 'text')

        proposed_price = data.get('proposed_price')
        if message_type == 'negotiation':
            if not await self.is_agent_sender():
                await self._send_error('forbidden', 'Seul l\'agent peut proposer un tarif')
                return
            try:
                proposed_price = float(proposed_price)
                if proposed_price <= 0:
                    raise ValueError()
            except (TypeError, ValueError):
                await self._send_error('invalid_price', 'Montant proposé invalide')
                return
            if not content:
                content = f'Proposition tarif : {proposed_price:.0f} FCFA'
        elif not content and message_type == 'text':
            await self._send_error('empty_content', 'Contenu vide')
            return

        # ── Déduplication ──
        if client_msg_id:
            existing = await self.find_by_client_id(client_msg_id)
            if existing:
                await self.send(text_data=json.dumps({
                    'type': 'message_ack',
                    'client_message_id': client_msg_id,
                    'message_id': str(existing.id),
                    'status': 'already_received',
                    'delivery_status': existing.delivery_status,
                }))
                return

        # ── Création + ACK + broadcast atomiques ──
        @database_sync_to_async
        @transaction.atomic
        def create_and_ack():
            extra = {}
            if message_type == 'negotiation':
                from decimal import Decimal
                extra['proposed_price'] = Decimal(str(proposed_price))
                extra['negotiation_status'] = Message.NegotiationStatus.PENDING
            message = Message.objects.create(
                conversation=self.conversation,
                sender=self.user,
                content=content,
                message_type=message_type,
                delivery_status=Message.DeliveryStatus.SENT,
                **extra,
                **({'client_message_id': uuid.UUID(client_msg_id)} if client_msg_id else {}),
            )
            return message

        try:
            message = await create_and_ack()
        except Exception as e:
            await self._send_error('save_failed', f'Impossible de sauvegarder: {e}')
            return

        msg_dict = _message_to_dict(message)

        # ── ACK au seul expéditeur ──
        await self.send(text_data=json.dumps({
            'type': 'message_ack',
            'client_message_id': client_msg_id,
            'message_id': str(message.id),
            'status': 'received',
            'delivery_status': Message.DeliveryStatus.SENT,
            'timestamp': message.created_at.isoformat(),
        }))

        # ── Diffusion au groupe ──
        await self.channel_layer.group_send(self.group_name, {
            'type': 'chat_message',
            'message': msg_dict,
            'sender_channel': self.channel_name,
        })

        # ── Marquer DELIVERED pour les connectés qui reçoivent ──
        await self.channel_layer.group_send(self.group_name, {
            'type': 'deliver_message',
            'message_id': str(message.id),
            'sender_channel': self.channel_name,
        })

    async def _handle_typing(self, data: dict, is_typing: bool):
        expiry = timezone.now() + timedelta(seconds=TYPING_EXPIRY_SECONDS) if is_typing else None
        await self.update_typing_status(is_typing, expiry)

        await self.channel_layer.group_send(self.group_name, {
            'type': 'typing_indicator',
            'user_id': str(self.user.id),
            'username': self.user.username,
            'is_typing': is_typing,
            'sender_channel': self.channel_name,
        })

    async def _handle_mark_read(self, data: dict):
        message_ids = data.get('message_ids', [])
        conversation_open = data.get('conversation_open', False)
        if not message_ids:
            return
        
        # Ne marquer comme READ que si la conversation est ouverte
        if conversation_open:
            count = await self.mark_messages_read(message_ids)
        else:
            # Conversation non ouverte : ne pas marquer READ, rester DELIVERED
            count = 0
        
        # Notifier l'expéditeur original que ses messages ont été lus (ou non)
        await self.channel_layer.group_send(self.group_name, {
            'type': 'read_receipt',
            'message_ids': message_ids,
            'reader_id': str(self.user.id),
            'reader': self.user.username,
            'read_at': timezone.now().isoformat(),
            'count': count,
            'conversation_open': conversation_open,
        })

    async def _handle_catchup(self, data: dict):
        """Envoie tous les messages postérieurs à last_message_id."""
        last_id = data.get('last_message_id')
        messages = await self.get_messages_after(last_id)
        await self.send(text_data=json.dumps({
            'type': 'catchup_result',
            'messages': [_message_to_dict(m) for m in messages],
            'count': len(messages),
        }))

    # ──────────────────────────────────────────────────────────────────────────
    # Handlers de groupe → WebSocket individuel
    # ──────────────────────────────────────────────────────────────────────────

    async def chat_message(self, event):
        """Reçoit un message du groupe et le transmet au client WebSocket."""
        if event.get('sender_channel') == self.channel_name:
            return  # Ne pas renvoyer à l'expéditeur (il a déjà l'ACK)
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
        }))

    async def deliver_message(self, event):
        """Marque un message comme DELIVERED pour les destinataires connectés."""
        if event.get('sender_channel') == self.channel_name:
            return  # L'expéditeur ne se délivre pas à lui-même
        msg_id = event['message_id']
        await self.set_message_delivered(msg_id)
        await self.send(text_data=json.dumps({
            'type': 'delivery_status',
            'message_id': msg_id,
            'delivery_status': Message.DeliveryStatus.DELIVERED,
            'delivered_at': timezone.now().isoformat(),
        }))

    async def typing_indicator(self, event):
        if event.get('sender_channel') == self.channel_name:
            return
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user_id': event['user_id'],
            'username': event['username'],
            'is_typing': event['is_typing'],
        }))

    async def read_receipt(self, event):
        await self.send(text_data=json.dumps({
            'type': 'read_receipt',
            'message_ids': event['message_ids'],
            'reader_id': event['reader_id'],
            'reader': event['reader'],
            'read_at': event['read_at'],
        }))

    async def presence_update(self, event):
        if event.get('user_id') == str(self.user.id):
            return  # Ne pas s'envoyer sa propre présence
        await self.send(text_data=json.dumps({
            'type': 'presence',
            'user_id': event['user_id'],
            'username': event['username'],
            'is_online': event['is_online'],
            'last_seen': event['last_seen'],
        }))

    async def system_message(self, event):
        """Messages système diffusés depuis les vues mission."""
        await self.send(text_data=json.dumps({
            'type': 'system_message',
            'message': event['message'],
        }))

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    async def _send_error(self, code: str, detail: str):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'code': code,
            'message': detail,
        }))

    # ──────────────────────────────────────────────────────────────────────────
    # DB (sync → async)
    # ──────────────────────────────────────────────────────────────────────────

    @database_sync_to_async
    def get_or_create_conversation(self):
        from apps.missions.models import Mission
        try:
            mission = Mission.objects.get(pk=self.mission_id)
            if mission.agent is not None:
                conv, _ = Conversation.objects.get_or_create(
                    mission=mission,
                    client=mission.client,
                    agent=mission.agent,
                )
            else:
                conv = Conversation.objects.filter(
                    mission=mission, client=mission.client
                ).first()
                if conv is None:
                    conv = Conversation.objects.create(
                        mission=mission,
                        client=mission.client,
                        agent=None,
                    )
            return conv
        except Mission.DoesNotExist:
            return None

    @database_sync_to_async
    def is_participant(self) -> bool:
        return (
            self.conversation.client_id == self.user.pk
            or self.conversation.agent_id == self.user.pk
        )

    @database_sync_to_async
    def is_agent_sender(self) -> bool:
        return self.conversation.agent_id == self.user.pk

    @database_sync_to_async
    def find_by_client_id(self, client_msg_id: str):
        try:
            return Message.objects.get(client_message_id=uuid.UUID(client_msg_id))
        except (Message.DoesNotExist, ValueError):
            return None

    @database_sync_to_async
    def create_message(self, content: str, message_type: str, client_msg_id) -> Message | None:
        try:
            kwargs: dict = {
                'conversation': self.conversation,
                'sender': self.user,
                'content': content,
                'message_type': message_type,
                'delivery_status': Message.DeliveryStatus.SENT,
            }
            if client_msg_id:
                try:
                    kwargs['client_message_id'] = uuid.UUID(client_msg_id)
                except ValueError:
                    pass
            return Message.objects.create(**kwargs)
        except Exception:
            return None

    @database_sync_to_async
    def mark_messages_read(self, message_ids: list) -> int:
        now = timezone.now()
        qs = Message.objects.filter(
            id__in=message_ids,
            conversation=self.conversation,
        ).exclude(sender=self.user)
        count = qs.update(
            is_read=True,
            read_at=now,
            delivery_status=Message.DeliveryStatus.READ,
        )
        # Mettre à jour last_read de l'utilisateur
        if self.conversation.client_id == self.user.pk:
            Conversation.objects.filter(pk=self.conversation.pk).update(client_last_read=now)
        else:
            Conversation.objects.filter(pk=self.conversation.pk).update(agent_last_read=now)
        return count

    @database_sync_to_async
    def set_message_delivered(self, message_id: str):
        Message.objects.filter(
            id=message_id,
            delivery_status=Message.DeliveryStatus.SENT,
        ).update(
            delivered_at=timezone.now(),
            delivery_status=Message.DeliveryStatus.DELIVERED,
        )

    @database_sync_to_async
    def get_messages_after(self, last_message_id) -> list:
        qs = Message.objects.filter(conversation=self.conversation).order_by('created_at')
        if last_message_id:
            try:
                ref = Message.objects.get(id=int(last_message_id))
                qs = qs.filter(created_at__gt=ref.created_at)
            except (Message.DoesNotExist, ValueError, TypeError):
                pass
        return list(qs.select_related('sender')[:200])

    @database_sync_to_async
    def update_typing_status(self, is_typing: bool, expires_at):
        obj, _ = TypingStatus.objects.update_or_create(
            conversation=self.conversation,
            user=self.user,
            defaults={'is_typing': is_typing, 'expires_at': expires_at},
        )
        return obj

    @database_sync_to_async
    def set_presence(self, online: bool):
        presence, _ = UserPresence.objects.get_or_create(user=self.user)
        if online:
            presence.mark_online()
        else:
            presence.mark_offline()
