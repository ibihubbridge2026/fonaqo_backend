from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .models import Conversation, Message, TypingStatus
from apps.missions.models import Mission
from apps.accounts.models import AgentProfile

User = get_user_model()


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
