import uuid

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from .models import Conversation, Message, TypingStatus, ChatAttachment, UserPresence

User = get_user_model()


def _make_users(client_kw='clientuser', agent_kw='agentuser'):
    client = User.objects.create_user(username=client_kw, password='pass',
                                       email=f'{client_kw}@test.local')
    agent  = User.objects.create_user(username=agent_kw,  password='pass',
                                       email=f'{agent_kw}@test.local')
    return client, agent


def _make_conv(client, agent):
    return Conversation.objects.create(client=client, agent=agent)


def _make_message(conv, sender, content='Hello', client_message_id=None):
    kwargs = dict(conversation=conv, sender=sender, content=content,
                  message_type='text', delivery_status=Message.DeliveryStatus.SENT)
    if client_message_id:
        kwargs['client_message_id'] = client_message_id
    return Message.objects.create(**kwargs)


# ─── Déduplication REST ───────────────────────────────────────────────────────

class TestRestMessageDeduplication(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.client_user, self.agent = _make_users()
        self.conv = _make_conv(self.client_user, self.agent)
        self.api.force_authenticate(user=self.client_user)

    def test_same_client_message_id_returns_existing(self):
        cid = uuid.uuid4()
        _make_message(self.conv, self.client_user, client_message_id=cid)
        resp = self.api.post(f'/api/chat/conversations/{self.conv.id}/send_message/', {
            'conversation': self.conv.id,
            'content': 'Duplicate message',
            'message_type': 'text',
            'client_message_id': str(cid),
        })
        self.assertIn(resp.status_code, [200, 201])
        self.assertEqual(Message.objects.filter(client_message_id=cid).count(), 1)

    def test_different_client_message_id_creates_new(self):
        _make_message(self.conv, self.client_user, client_message_id=uuid.uuid4())
        resp = self.api.post(f'/api/chat/conversations/{self.conv.id}/send_message/', {
            'conversation': self.conv.id,
            'content': 'New message',
            'message_type': 'text',
            'client_message_id': str(uuid.uuid4()),
        })
        self.assertEqual(resp.status_code, 201)


# ─── Statuts de livraison ─────────────────────────────────────────────────────

class TestDeliveryStatus(TestCase):
    def setUp(self):
        self.client_user, self.agent = _make_users('cu2', 'au2')
        self.conv = _make_conv(self.client_user, self.agent)

    def test_default_status_is_sent(self):
        msg = _make_message(self.conv, self.client_user)
        self.assertEqual(msg.delivery_status, Message.DeliveryStatus.SENT)

    def test_mark_as_delivered(self):
        msg = _make_message(self.conv, self.client_user)
        msg.mark_as_delivered()
        msg.refresh_from_db()
        self.assertEqual(msg.delivery_status, Message.DeliveryStatus.DELIVERED)
        self.assertIsNotNone(msg.delivered_at)

    def test_mark_as_read_updates_both_fields(self):
        msg = _make_message(self.conv, self.client_user)
        msg.mark_as_read()
        msg.refresh_from_db()
        self.assertEqual(msg.delivery_status, Message.DeliveryStatus.READ)
        self.assertTrue(msg.is_read)
        self.assertIsNotNone(msg.read_at)

    def test_mark_delivered_noop_if_already_delivered(self):
        msg = _make_message(self.conv, self.client_user)
        msg.mark_as_delivered()
        delivered_at_1 = msg.delivered_at
        msg.mark_as_delivered()  # should be noop
        msg.refresh_from_db()
        self.assertEqual(msg.delivered_at, delivered_at_1)


# ─── messages_after (rattrapage reconnect) ───────────────────────────────────

class TestMessagesAfter(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.client_user, self.agent = _make_users('cu3', 'au3')
        self.conv = _make_conv(self.client_user, self.agent)
        self.api.force_authenticate(user=self.client_user)
        self.m1 = _make_message(self.conv, self.client_user, 'msg1')
        self.m2 = _make_message(self.conv, self.client_user, 'msg2')
        self.m3 = _make_message(self.conv, self.client_user, 'msg3')

    def test_returns_messages_after_given_id(self):
        resp = self.api.get(
            f'/api/chat/conversations/{self.conv.id}/messages_after/',
            {'last_message_id': self.m1.id},
        )
        self.assertEqual(resp.status_code, 200)
        ids = [m['id'] for m in resp.data]
        self.assertIn(str(self.m2.id), ids)
        self.assertIn(str(self.m3.id), ids)
        self.assertNotIn(str(self.m1.id), ids)

    def test_no_last_id_returns_all(self):
        resp = self.api.get(f'/api/chat/conversations/{self.conv.id}/messages_after/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data), 3)


# ─── ChatAttachment ───────────────────────────────────────────────────────────

class TestChatAttachment(TestCase):
    def setUp(self):
        self.client_user, self.agent = _make_users('cu4', 'au4')
        self.conv = _make_conv(self.client_user, self.agent)
        self.msg  = _make_message(self.conv, self.client_user)

    def test_create_attachment(self):
        att = ChatAttachment.objects.create(
            message=self.msg,
            attachment_type='image',
            file='chat_attachments/test.jpg',
            original_filename='photo.jpg',
            file_size=1024,
            mime_type='image/jpeg',
        )
        self.assertEqual(att.attachment_type, 'image')
        self.assertEqual(self.msg.attachments.count(), 1)


# ─── UserPresence ─────────────────────────────────────────────────────────────

class TestUserPresence(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='presuser', password='p',
                                             email='presuser@test.local')

    def test_mark_online_offline(self):
        p, _ = UserPresence.objects.get_or_create(user=self.user)
        p.mark_online()
        self.assertTrue(p.is_online)
        p.mark_offline()
        self.assertFalse(p.is_online)


# ─── Messages système ─────────────────────────────────────────────────────────

class TestSendSystemMessage(TestCase):
    """
    Teste send_system_message en mockant la Mission (évite le PointField GIS).
    """
    from unittest.mock import MagicMock, patch

    def setUp(self):
        self.client_user, self.agent = _make_users('sys_c', 'sys_a')
        self.conv = _make_conv(self.client_user, self.agent)

    def _make_mock_mission(self, has_conversation=True):
        from unittest.mock import MagicMock
        mission = MagicMock()
        mission.id = uuid.uuid4()
        mission.client = self.client_user
        mission.agent  = self.agent
        if has_conversation:
            self.conv.mission_id = mission.id
            # Patch Conversation.objects.filter to return our conv
        return mission

    @patch('apps.chat.views.Conversation')
    def test_system_message_created(self, MockConv):
        from apps.chat.views import send_system_message
        mission = self._make_mock_mission()
        MockConv.objects.filter.return_value.first.return_value = self.conv
        msg = send_system_message(mission, "Mission démarrée")
        self.assertIsNotNone(msg)
        self.assertEqual(msg.message_type, 'system')
        self.assertEqual(msg.content, "Mission démarrée")

    @patch('apps.chat.views.Conversation')
    def test_system_message_none_without_conversation(self, MockConv):
        from apps.chat.views import send_system_message
        mission = self._make_mock_mission(has_conversation=False)
        MockConv.objects.filter.return_value.first.return_value = None
        result = send_system_message(mission, "Aucune conversation")
        self.assertIsNone(result)


class ConversationViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Créer utilisateurs
        self.client_user = User.objects.create_user(
            username='testclient',
            email='client@test.com',
            password='testpass123'
        )
        
        self.agent_user = User.objects.create_user(
            username='testagent',
            email='agent@test.com',
            password='testpass123'
        )
        self.agent_profile = AgentProfile.objects.create(
            user=self.agent_user,
            phone_number='+225000000000',
            is_verified=True
        )
        
        # Créer une mission
        self.mission = Mission.objects.create(
            client=self.client_user,
            assigned_agent=self.agent_profile,
            title='Test Mission',
            description='Test Description',
            price=10000.00,
            status='in_progress'
        )
        
        # Créer une conversation
        self.conversation = Conversation.objects.create(
            mission=self.mission,
            client=self.client_user,
            agent=self.agent_user
        )
    
    def test_create_conversation(self):
        """Test créer une conversation"""
        self.client.force_authenticate(user=self.client_user)
        
        response = self.client.post('/api/chat-enhanced/conversations/', {
            'mission': self.mission.id,
            'client': self.client_user.id,
            'agent': self.agent_user.id
        })
        
        # La conversation existe déjà, donc on devrait avoir une erreur
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_get_my_conversations(self):
        """Test obtenir mes conversations"""
        self.client.force_authenticate(user=self.client_user)
        
        response = self.client.get('/api/chat-enhanced/conversations/my_conversations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_send_message(self):
        """Test envoyer un message"""
        self.client.force_authenticate(user=self.client_user)
        
        response = self.client.post(f'/api/chat-enhanced/conversations/{self.conversation.id}/send_message/', {
            'message_type': 'text',
            'content': 'Hello, this is a test message'
        })
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Message.objects.count(), 1)
    
    def test_get_conversation_messages(self):
        """Test obtenir les messages d'une conversation"""
        self.client.force_authenticate(user=self.client_user)
        
        # Créer un message
        Message.objects.create(
            conversation=self.conversation,
            sender=self.client_user,
            message_type='text',
            content='Test message'
        )
        
        response = self.client.get(f'/api/chat-enhanced/conversations/{self.conversation.id}/messages/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_mark_messages_as_read(self):
        """Test marquer des messages comme lus"""
        self.client.force_authenticate(user=self.agent_user)
        
        # Créer un message du client
        Message.objects.create(
            conversation=self.conversation,
            sender=self.client_user,
            message_type='text',
            content='Test message'
        )
        
        response = self.client.post(f'/api/chat-enhanced/conversations/{self.conversation.id}/mark_read/', {
            'mark_all': True
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['marked_count'], 1)
    
    def test_update_typing_status(self):
        """Test mettre à jour le statut de frappe"""
        self.client.force_authenticate(user=self.client_user)
        
        response = self.client.post(f'/api/chat-enhanced/conversations/{self.conversation.id}/typing_status/', {
            'is_typing': True
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['is_typing'], True)
    
    def test_archive_conversation(self):
        """Test archiver une conversation"""
        self.client.force_authenticate(user=self.client_user)
        
        response = self.client.post(f'/api/chat-enhanced/conversations/{self.conversation.id}/archive/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.conversation.refresh_from_db()
        self.assertTrue(self.conversation.is_archived)


class MessageViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        self.client_user = User.objects.create_user(
            username='testclient',
            email='client@test.com',
            password='testpass123'
        )
        
        self.agent_user = User.objects.create_user(
            username='testagent',
            email='agent@test.com',
            password='testpass123'
        )
        self.agent_profile = AgentProfile.objects.create(
            user=self.agent_user,
            phone_number='+225000000000',
            is_verified=True
        )
        
        self.mission = Mission.objects.create(
            client=self.client_user,
            assigned_agent=self.agent_profile,
            title='Test Mission',
            description='Test Description',
            price=10000.00,
            status='in_progress'
        )
        
        self.conversation = Conversation.objects.create(
            mission=self.mission,
            client=self.client_user,
            agent=self.agent_user
        )
        
        self.message = Message.objects.create(
            conversation=self.conversation,
            sender=self.client_user,
            message_type='text',
            content='Test message'
        )
    
    def test_get_messages(self):
        """Test obtenir les messages"""
        self.client.force_authenticate(user=self.client_user)
        
        response = self.client.get('/api/chat-enhanced/messages/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
