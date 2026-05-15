from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()


class BoostsPermissionsTest(TestCase):
    """Test des permissions pour l'app Boosts"""
    
    def setUp(self):
        self.client = APIClient()
        # Ne pas authentifier le client pour tester les permissions
    
    def test_unauthenticated_access_denied(self):
        """Test que les requêtes non authentifiées renvoient 401"""
        response = self.client.get('/api/v1/boosts/plans/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        response = self.client.get('/api/v1/boosts/my-boosts/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        response = self.client.post('/api/v1/boosts/my-boosts/', {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
