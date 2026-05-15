from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .models import Dispute, DisputeEvidence, DisputeComment
from apps.missions.models import Mission
from apps.accounts.models import AgentProfile

User = get_user_model()


class DisputeViewSetTest(TestCase):
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
        
        self.staff_user = User.objects.create_user(
            username='staff',
            email='staff@test.com',
            password='testpass123',
            is_staff=True
        )
        
        # Créer une mission
        self.mission = Mission.objects.create(
            client=self.client_user,
            assigned_agent=self.agent_profile,
            title='Test Mission',
            description='Test Description',
            price=10000.00,
            status='completed'
        )
        
        # Créer un litige
        self.dispute = Dispute.objects.create(
            mission=self.mission,
            opened_by=self.client_user,
            title='Test Dispute',
            description='Test Description',
            priority='medium'
        )
    
    def test_create_dispute_as_client(self):
        """Test créer un litige en tant que client"""
        self.client.force_authenticate(user=self.client_user)
        
        response = self.client.post('/api/disputes/', {
            'mission': self.mission.id,
            'title': 'New Dispute',
            'description': 'New Description',
            'priority': 'high'
        })
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Dispute.objects.count(), 2)
    
    def test_get_my_disputes(self):
        """Test obtenir mes litiges"""
        self.client.force_authenticate(user=self.client_user)
        
        response = self.client.get('/api/disputes/my_disputes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_resolve_dispute_as_staff(self):
        """Test résoudre un litige en tant que staff"""
        self.client.force_authenticate(user=self.staff_user)
        
        response = self.client.post(f'/api/disputes/{self.dispute.id}/resolve/', {
            'status': 'resolved',
            'resolution_notes': 'Issue resolved',
            'refund_amount': 5000.00
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Vérifier que le statut a changé
        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.status, 'resolved')
    
    def test_add_evidence_to_dispute(self):
        """Test ajouter une preuve à un litige"""
        self.client.force_authenticate(user=self.client_user)
        
        # Simuler un fichier upload
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        test_file = SimpleUploadedFile(
            "test.jpg",
            b"file_content",
            content_type="image/jpeg"
        )
        
        response = self.client.post(f'/api/disputes/{self.dispute.id}/add_evidence/', {
            'file': test_file,
            'description': 'Test evidence'
        })
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DisputeEvidence.objects.count(), 1)
    
    def test_get_dispute_stats_as_staff(self):
        """Test obtenir les stats des litiges"""
        self.client.force_authenticate(user=self.staff_user)
        
        response = self.client.get('/api/disputes/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_disputes', response.data)
        self.assertIn('open_disputes', response.data)
