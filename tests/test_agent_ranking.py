"""Tests pour le système de classement des agents."""

from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point

from apps.accounts.models import AgentProfile
from apps.core.choices import MissionStatus, AgentKYCStatus
from apps.missions.models import Mission
from apps.accounts.agent_ranking_service import AgentRankingService

User = get_user_model()


def _make_user(username, is_agent=False, is_client=False):
    """Helper pour créer un utilisateur."""
    import random
    return User.objects.create_user(
        username=username,
        email=f'{username}@test.com',
        phone_number=f'+229{random.randint(10000000, 99999999)}',
        is_agent=is_agent,
        is_client=is_client,
        is_verified=True,
    )


class AgentRankingTest(TestCase):
    """Tests du système de classement des agents."""

    def setUp(self):
        self.agent1 = _make_user('agent1', is_agent=True)
        self.agent2 = _make_user('agent2', is_agent=True)
        self.client = _make_user('client', is_client=True)
        
        # Créer les AgentProfile
        AgentProfile.objects.create(
            user=self.agent1,
            kyc_status=AgentKYCStatus.APPROVED,
            agent_code='AGT-00001'
        )
        AgentProfile.objects.create(
            user=self.agent2,
            kyc_status=AgentKYCStatus.APPROVED,
            agent_code='AGT-00002'
        )

    def test_ranking_formula(self):
        """Teste la formule de calcul du score de classement."""
        profile1 = self.agent1.agent_profile
        
        # Cas 1: Agent parfait (note 5, complétion 100%, réponse rapide, beaucoup de missions)
        profile1.average_rating = Decimal('5.00')
        profile1.completion_rate = 100.0
        profile1.response_time_avg = 300.0  # 5 minutes
        profile1.ratings_count = 100
        
        score = AgentRankingService.calculate_ranking_score(profile1)
        
        # Score attendu ~ 40 (rating) + 30 (completion) + 20 (response) + 10 (volume) = 100
        self.assertGreater(score, 90)
        self.assertLessEqual(score, 100)
        
        # Cas 2: Agent moyen (note 3, complétion 70%, réponse lent, peu de missions)
        profile1.average_rating = Decimal('3.00')
        profile1.completion_rate = 70.0
        profile1.response_time_avg = 1800.0  # 30 minutes
        profile1.ratings_count = 5
        
        score = AgentRankingService.calculate_ranking_score(profile1)
        
        # Score attendu ~ 24 (rating) + 21 (completion) + ~10 (response) + ~2 (volume) = ~57
        self.assertGreater(score, 40)
        self.assertLess(score, 70)

    def test_ranking_order(self):
        """Teste que les agents sont correctement classés par score."""
        profile1 = self.agent1.agent_profile
        profile2 = self.agent2.agent_profile
        
        # Agent 1: meilleur score
        profile1.average_rating = Decimal('5.00')
        profile1.completion_rate = 100.0
        profile1.response_time_avg = 300.0
        profile1.ratings_count = 50
        profile1.ranking_score = AgentRankingService.calculate_ranking_score(profile1)
        profile1.save()
        
        # Agent 2: moins bon score
        profile2.average_rating = Decimal('3.00')
        profile2.completion_rate = 50.0
        profile2.response_time_avg = 3600.0
        profile2.ratings_count = 5
        profile2.ranking_score = AgentRankingService.calculate_ranking_score(profile2)
        profile2.save()
        
        # Récupérer les top agents
        top_agents = AgentRankingService.get_top_agents(limit=10)
        
        # Agent 1 doit être premier
        self.assertEqual(len(top_agents), 2)
        self.assertEqual(top_agents[0].user, self.agent1)
        self.assertEqual(top_agents[1].user, self.agent2)
        self.assertGreater(top_agents[0].ranking_score, top_agents[1].ranking_score)

    def test_ranking_update(self):
        """Teste la mise à jour du score de classement."""
        profile = self.agent1.agent_profile
        
        # Score initial bas
        profile.average_rating = Decimal('2.00')
        profile.completion_rate = 30.0
        profile.response_time_avg = 3600.0
        profile.ratings_count = 2
        profile.ranking_score = AgentRankingService.calculate_ranking_score(profile)
        profile.save()
        
        initial_score = profile.ranking_score
        
        # Améliorer les métriques et sauvegarder
        profile.average_rating = Decimal('4.50')
        profile.completion_rate = 90.0
        profile.response_time_avg = 400.0
        profile.ratings_count = 20
        profile.save()
        
        # Mettre à jour via le service
        AgentRankingService.update_agent_ranking(self.agent1.id)
        
        # Recharger et vérifier
        profile.refresh_from_db()
        self.assertGreater(profile.ranking_score, initial_score)

    def test_ranking_clamp(self):
        """Teste que le score est clampé entre 0 et 100."""
        profile = self.agent1.agent_profile
        
        # Cas extrême: tout à 0
        profile.average_rating = Decimal('0.00')
        profile.completion_rate = 0.0
        profile.response_time_avg = 10000.0  # Très lent
        profile.ratings_count = 0
        
        score = AgentRankingService.calculate_ranking_score(profile)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)
        
        # Cas extrême: tout au maximum
        profile.average_rating = Decimal('5.00')
        profile.completion_rate = 100.0
        profile.response_time_avg = 0.0  # Instantané
        profile.ratings_count = 10000
        
        score = AgentRankingService.calculate_ranking_score(profile)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)
