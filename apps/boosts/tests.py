from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .models import BoostPlan, AgentBoost
from apps.accounts.models import AgentProfile

User = get_user_model()


class BoostPlanViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testagent',
            email='agent@test.com',
            password='testpass123'
        )
        self.agent_profile = AgentProfile.objects.create(
            user=self.user,
            phone_number='+225000000000',
            is_verified=True
        )
        self.client.force_authenticate(user=self.user)
        
        # Créer un plan de boost
        self.boost_plan = BoostPlan.objects.create(
            name='Day Boost',
            duration_hours=24,
            price=5000.00,
            description='Boost de 24h',
            visibility_multiplier=2.0
        )
    
    def test_get_boost_plans(self):
        """Test obtenir la liste des plans de boost"""
        response = self.client.get('/api/boosts/plans/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Day Boost')
    
    def test_calculate_boost_cost(self):
        """Test calculer le coût d'un boost"""
        response = self.client.post('/api/boosts/plans/calculate_cost/', {
            'plan_id': self.boost_plan.id
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['price'], '5000.00')
    
    def test_create_agent_boost(self):
        """Test créer un boost pour un agent"""
        response = self.client.post('/api/boosts/my-boosts/', {
            'plan': self.boost_plan.id,
            'purchase_amount': 5000.00,
            'transaction_id': 'TX123456'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AgentBoost.objects.count(), 1)
    
    def test_get_active_boost(self):
        """Test obtenir le boost actif"""
        # Créer un boost
        AgentBoost.objects.create(
            agent=self.agent_profile,
            plan=self.boost_plan,
            purchase_amount=5000.00,
            status='active'
        )
        
        response = self.client.get('/api/boosts/my-boosts/active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'active')


class AgentBoostViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testagent',
            email='agent@test.com',
            password='testpass123'
        )
        self.agent_profile = AgentProfile.objects.create(
            user=self.user,
            phone_number='+225000000000',
            is_verified=True
        )
        self.client.force_authenticate(user=self.user)
        
        self.boost_plan = BoostPlan.objects.create(
            name='Day Boost',
            duration_hours=24,
            price=5000.00,
            description='Boost de 24h',
            visibility_multiplier=2.0
        )
    
    def test_boost_history(self):
        """Test obtenir l'historique des boosts"""
        # Créer quelques boosts
        for i in range(3):
            AgentBoost.objects.create(
                agent=self.agent_profile,
                plan=self.boost_plan,
                purchase_amount=5000.00,
                status='expired'
            )
        
        response = self.client.get('/api/boosts/my-boosts/history/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
