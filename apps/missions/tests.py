from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .models import MissionProof, MissionTimelineEvent, AgentStatistics
from apps.missions.models import Mission
from apps.accounts.models import AgentProfile
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()


class MissionProofViewSetTest(TestCase):
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
            status='completed'
        )
        
        self.client.force_authenticate(user=self.agent_user)
    
    def test_create_mission_proof(self):
        """Test créer une preuve de mission"""
        test_file = SimpleUploadedFile(
            "test.jpg",
            b"file_content",
            content_type="image/jpeg"
        )
        
        response = self.client.post('/api/missions-enhanced/proofs/', {
            'mission': self.mission.id,
            'image': test_file,
            'caption': 'Test proof',
            'is_primary': False,
            'location_lat': 5.3600,
            'location_lng': -4.0083
        })
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MissionProof.objects.count(), 1)
    
    def test_get_mission_proofs(self):
        """Test obtenir les preuves d'une mission"""
        # Créer une preuve
        test_file = SimpleUploadedFile(
            "test.jpg",
            b"file_content",
            content_type="image/jpeg"
        )
        
        MissionProof.objects.create(
            mission=self.mission,
            uploaded_by=self.agent_user,
            image=test_file,
            caption='Test proof'
        )
        
        response = self.client.get('/api/missions-enhanced/proofs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_set_proof_as_primary(self):
        """Test définir une preuve comme principale"""
        # Créer une preuve
        test_file = SimpleUploadedFile(
            "test.jpg",
            b"file_content",
            content_type="image/jpeg"
        )
        
        proof = MissionProof.objects.create(
            mission=self.mission,
            uploaded_by=self.agent_user,
            image=test_file,
            caption='Test proof'
        )
        
        response = self.client.post(f'/api/missions-enhanced/proofs/{proof.id}/set_primary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        proof.refresh_from_db()
        self.assertTrue(proof.is_primary)


class MissionTimelineEventViewSetTest(TestCase):
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
        
        self.client.force_authenticate(user=self.agent_user)
    
    def test_create_timeline_event(self):
        """Test créer un événement de timeline"""
        response = self.client.post('/api/missions-enhanced/timeline/', {
            'mission': self.mission.id,
            'event_type': 'agent_arrived',
            'notes': 'Agent arrived on location',
            'location_lat': 5.3600,
            'location_lng': -4.0083
        })
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MissionTimelineEvent.objects.count(), 1)
    
    def test_get_mission_timeline(self):
        """Test obtenir la timeline d'une mission"""
        # Créer un événement
        MissionTimelineEvent.objects.create(
            mission=self.mission,
            event_type='agent_arrived',
            performed_by=self.agent_user,
            notes='Agent arrived on location'
        )
        
        response = self.client.get('/api/missions-enhanced/timeline/mission_timeline/', {
            'mission_id': self.mission.id
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class AgentStatisticsViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        self.agent_user = User.objects.create_user(
            username='testagent',
            email='agent@test.com',
            password='testpass123'
        )
        self.agent_profile = AgentProfile.objects.create(
            user=self.agent_user,
            phone_number='+225000000000',
            is_verified=True,
            rating=4.5
        )
        
        self.client.force_authenticate(user=self.agent_user)
        
        # Créer quelques missions
        for i in range(5):
            Mission.objects.create(
                client=User.objects.create_user(
                    username=f'client{i}',
                    email=f'client{i}@test.com',
                    password='testpass123'
                ),
                assigned_agent=self.agent_profile,
                title=f'Mission {i}',
                description='Test Description',
                price=10000.00,
                status='completed' if i < 3 else 'pending'
            )
    
    def test_get_dashboard_stats(self):
        """Test obtenir les stats du dashboard"""
        response = self.client.get('/api/missions-enhanced/statistics/dashboard_stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertIn('total_missions', data)
        self.assertIn('completed_missions', data)
        self.assertIn('total_earnings', data)
        self.assertIn('level', data)
    
    def test_get_performance_stats(self):
        """Test obtenir les stats de performance"""
        response = self.client.get('/api/missions-enhanced/statistics/performance_stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertIn('total_missions', data)
        self.assertIn('completion_rate', data)
        self.assertIn('level', data)
    
    def test_update_stats(self):
        """Test mettre à jour les statistiques"""
        response = self.client.post('/api/missions-enhanced/statistics/update_stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Vérifier que les stats ont été créées
        stats = AgentStatistics.objects.filter(agent=self.agent_profile).first()
        self.assertIsNotNone(stats)
        self.assertEqual(stats.total_missions, 5)
        self.assertEqual(stats.completed_missions, 3)
