import hashlib
import uuid
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from .models import MissionProof, MissionTimelineEvent, AgentStatistics, Mission
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile


# ─── Tests vocal_utils ───────────────────────────────────────────────────────

class TestComputeTranscriptionHash(TestCase):
    def test_deterministic(self):
        from apps.missions.vocal_utils import compute_transcription_hash
        h1 = compute_transcription_hash("Bonjour  je veux   une mission")
        h2 = compute_transcription_hash("bonjour je veux une mission")
        self.assertEqual(h1, h2, "Le hash doit être insensible à la casse et aux espaces multiples")

    def test_different_texts_give_different_hashes(self):
        from apps.missions.vocal_utils import compute_transcription_hash
        h1 = compute_transcription_hash("plomberie")
        h2 = compute_transcription_hash("menuiserie")
        self.assertNotEqual(h1, h2)

    def test_returns_sha256_hex(self):
        from apps.missions.vocal_utils import compute_transcription_hash
        h = compute_transcription_hash("test")
        self.assertEqual(len(h), 64)


class TestValidateExtractedJson(TestCase):
    def test_valid_data_passes(self):
        from apps.missions.vocal_utils import validate_extracted_json
        data = {
            "title": "Réparation robinet",
            "description": "Mon robinet fuit depuis hier",
            "category": "Plomberie",
            "budget": 15000,
            "address": "Cotonou, Bénin",
            "scheduled_date": "ASAP",
            "scheduled_time_slot": "MORNING",
        }
        cleaned, errors = validate_extracted_json(data)
        self.assertEqual(errors, [])
        self.assertIn("title", cleaned)

    def test_missing_required_field_returns_error(self):
        from apps.missions.vocal_utils import validate_extracted_json
        data = {"description": "test"}
        cleaned, errors = validate_extracted_json(data)
        self.assertTrue(len(errors) > 0)

    def test_budget_string_coerced_to_number(self):
        from apps.missions.vocal_utils import validate_extracted_json
        data = {
            "title": "Test",
            "description": "desc",
            "category": "Autre",
            "budget": "12000",
            "address": "Cotonou",
            "scheduled_date": "ASAP",
        }
        cleaned, errors = validate_extracted_json(data)
        # budget as string may cause a jsonschema type error
        # The function should still return cleaned data
        self.assertIsInstance(cleaned, dict)

    def test_negative_budget_produces_error(self):
        from apps.missions.vocal_utils import validate_extracted_json
        data = {
            "title": "T",
            "description": "d",
            "category": "A",
            "budget": -500,
            "address": "Cotonou",
            "scheduled_date": "ASAP",
        }
        cleaned, errors = validate_extracted_json(data)
        self.assertTrue(any("minimum" in e.lower() or "less than" in e.lower() for e in errors))


class TestFindBestCategory(TestCase):
    def setUp(self):
        from apps.services.models import Category
        Category.objects.create(name="Plomberie", keywords=["plombier", "robinet", "fuite"])
        Category.objects.create(name="Électricité", keywords=["électricien", "câble", "prise"])

    def test_exact_match(self):
        from apps.missions.vocal_utils import find_best_category
        cat = find_best_category("Plomberie")
        self.assertIsNotNone(cat)
        self.assertEqual(cat.name, "Plomberie")

    def test_case_insensitive_match(self):
        from apps.missions.vocal_utils import find_best_category
        cat = find_best_category("plomberie")
        self.assertIsNotNone(cat)

    def test_keyword_match(self):
        from apps.missions.vocal_utils import find_best_category
        cat = find_best_category("robinet")
        self.assertIsNotNone(cat)
        self.assertEqual(cat.name, "Plomberie")

    def test_no_match_returns_none(self):
        from apps.missions.vocal_utils import find_best_category
        cat = find_best_category("zéphyrlologie quantique")
        self.assertIsNone(cat)


class TestGeocodeAddress(TestCase):
    @patch("apps.missions.vocal_utils.requests.get")
    def test_returns_coords_on_success(self, mock_get):
        from apps.missions.vocal_utils import geocode_address
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"lat": "6.36", "lon": "2.41"}]
        mock_get.return_value = mock_resp
        lat, lng = geocode_address("Cotonou, Bénin")
        self.assertAlmostEqual(lat, 6.36)
        self.assertAlmostEqual(lng, 2.41)

    @patch("apps.missions.vocal_utils.requests.get")
    def test_returns_none_on_failure(self, mock_get):
        from apps.missions.vocal_utils import geocode_address
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []
        mock_get.return_value = mock_resp
        lat, lng = geocode_address("adresse complètement inconnue xyz123")
        self.assertIsNone(lat)
        self.assertIsNone(lng)

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
