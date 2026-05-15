from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .models import AgentStatistics
from apps.missions.models import Mission
from apps.accounts.models import AgentProfile

User = get_user_model()


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
        
        # Créer quelques missions pour les stats
        for i in range(10):
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
                status='completed' if i < 7 else 'cancelled'
            )
    
    def test_get_agent_statistics(self):
        """Test obtenir les statistiques d'un agent"""
        # Créer les stats de l'agent
        stats = AgentStatistics.objects.create(
            agent=self.agent_profile,
            total_missions=10,
            completed_missions=7,
            cancelled_missions=3,
            total_earnings=70000.00,
            average_rating=4.5,
            total_ratings=7,
            completion_rate=70.0
        )
        
        response = self.client.get('/api/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['total_missions'], 10)
    
    def test_get_performance_stats(self):
        """Test obtenir les stats de performance"""
        response = self.client.get('/api/statistics/performance_stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertIn('total_missions', data)
        self.assertIn('completed_missions', data)
        self.assertIn('completion_rate', data)
        self.assertIn('level', data)
        self.assertEqual(data['total_missions'], 10)
        self.assertEqual(data['completed_missions'], 7)
    
    def test_get_weekly_stats(self):
        """Test obtenir les stats hebdomadaires"""
        response = self.client.get('/api/statistics/weekly_stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertIn('week_start', data)
        self.assertIn('week_end', data)
        self.assertIn('missions_completed', data)
        self.assertIn('earnings', data)
    
    def test_get_monthly_stats(self):
        """Test obtenir les stats mensuelles"""
        response = self.client.get('/api/statistics/monthly_stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertIn('month', data)
        self.assertIn('year', data)
        self.assertIn('missions_completed', data)
        self.assertIn('earnings', data)
    
    def test_get_leaderboard(self):
        """Test obtenir le classement des agents"""
        # Créer un deuxième agent pour le classement
        agent2_user = User.objects.create_user(
            username='agent2',
            email='agent2@test.com',
            password='testpass123'
        )
        agent2_profile = AgentProfile.objects.create(
            user=agent2_user,
            phone_number='+225000000001',
            is_verified=True,
            rating=4.8
        )
        
        # Créer des missions pour le deuxième agent
        for i in range(5):
            Mission.objects.create(
                client=User.objects.create_user(
                    username=f'client2{i}',
                    email=f'client2{i}@test.com',
                    password='testpass123'
                ),
                assigned_agent=agent2_profile,
                title=f'Mission 2-{i}',
                description='Test Description',
                price=15000.00,
                status='completed'
            )
        
        response = self.client.get('/api/statistics/leaderboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertIn('leaderboard', data)
        self.assertIn('current_user_rank', data)
        self.assertTrue(len(data['leaderboard']) >= 1)
    
    def test_get_earnings_breakdown(self):
        """Test obtenir la répartition des revenus"""
        response = self.client.get('/api/statistics/earnings_breakdown/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertIn('period', data)
        self.assertIn('total_earnings', data)
        self.assertIn('earnings_by_category', data)
        self.assertIn('daily_average', data)
    
    def test_get_earnings_breakdown_with_period(self):
        """Test obtenir la répartition des revenus avec une période spécifique"""
        response = self.client.get('/api/statistics/earnings_breakdown/?period=week')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertEqual(data['period'], 'week')
        self.assertIn('total_earnings', data)
    
    def test_non_agent_cannot_access_stats(self):
        """Test qu'un non-agent ne peut pas accéder aux stats"""
        # Créer un utilisateur normal
        normal_user = User.objects.create_user(
            username='normaluser',
            email='normal@test.com',
            password='testpass123'
        )
        
        self.client.force_authenticate(user=normal_user)
        
        response = self.client.get('/api/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)  # Pas de stats pour un non-agent
