"""Tests pour le programme de fidélité clients."""

from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point

from apps.accounts.models import ClientRewardProfile
from apps.core.choices import MissionStatus
from apps.missions.models import Mission
from apps.accounts.loyalty_service import LoyaltyService

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


class LoyaltyTest(TestCase):
    """Tests du système de fidélité clients."""

    def setUp(self):
        self.client_user = _make_user('client', is_client=True)
        self.agent_user = _make_user('agent', is_agent=True)

    def test_points_awarded_on_mission_completion(self):
        """Teste que des points sont attribués quand une mission est complétée."""
        mission = Mission.objects.create(
            client=self.client_user,
            agent=self.agent_user,
            title='Test mission',
            description='Test',
            location=Point(2.4, 6.4),
            address='Cotonou',
            price=Decimal('5000'),
            status=MissionStatus.PENDING,
        )

        # Compléter la mission
        mission.status = MissionStatus.COMPLETED
        mission.save()

        # Vérifier que le profil a été créé
        profile = ClientRewardProfile.objects.get(user=self.client_user)
        self.assertEqual(profile.points, 10)  # Points de base
        self.assertEqual(profile.total_missions_completed, 1)
        self.assertEqual(profile.total_spent, Decimal('5000'))

    def test_high_value_mission_bonus_points(self):
        """Teste le bonus de points pour les missions haute valeur."""
        mission = Mission.objects.create(
            client=self.client_user,
            agent=self.agent_user,
            title='Test mission',
            description='Test',
            location=Point(2.4, 6.4),
            address='Cotonou',
            price=Decimal('15000'),  # > 10000 FCFA
            status=MissionStatus.PENDING,
        )

        mission.status = MissionStatus.COMPLETED
        mission.save()

        profile = ClientRewardProfile.objects.get(user=self.client_user)
        # Points: 10 (base) + 75 (bonus: 15k / 1k * 5) = 85
        self.assertEqual(profile.points, 85)

    def test_badge_unlock_first_mission(self):
        """Teste le déblocage du badge 'Première Mission'."""
        mission = Mission.objects.create(
            client=self.client_user,
            agent=self.agent_user,
            title='Test mission',
            description='Test',
            location=Point(2.4, 6.4),
            address='Cotonou',
            price=Decimal('5000'),
            status=MissionStatus.PENDING,
        )

        mission.status = MissionStatus.COMPLETED
        mission.save()

        profile = ClientRewardProfile.objects.get(user=self.client_user)
        self.assertIn('first_mission', profile.badges_unlocked)

    def test_level_progression(self):
        """Teste la progression de niveau avec les points."""
        profile = LoyaltyService.get_or_create_profile(self.client_user)
        
        # Niveau 1 (0-99 points)
        self.assertEqual(profile.level, 1)
        
        # Ajouter 100 points → Niveau 2
        profile.add_points(100)
        self.assertEqual(profile.level, 2)
        
        # Ajouter 200 points (total 300) → Niveau 3
        profile.add_points(200)
        self.assertEqual(profile.level, 3)

    def test_non_agent_no_points(self):
        """Teste qu'un agent ne gagne pas de points comme client."""
        mission = Mission.objects.create(
            client=self.agent_user,  # Agent comme client
            agent=self.agent_user,
            title='Test mission',
            description='Test',
            location=Point(2.4, 6.4),
            address='Cotonou',
            price=Decimal('5000'),
            status=MissionStatus.PENDING,
        )

        mission.status = MissionStatus.COMPLETED
        mission.save()

        # Pas de profil créé pour un agent non-client
        self.assertFalse(ClientRewardProfile.objects.filter(user=self.agent_user).exists())

    def test_get_client_rewards(self):
        """Teste la récupération des récompenses client."""
        rewards = LoyaltyService.get_client_rewards(self.client_user)
        
        self.assertIsNotNone(rewards)
        self.assertEqual(rewards['points'], 0)
        self.assertEqual(rewards['level'], 1)
        self.assertEqual(rewards['total_missions_completed'], 0)
        self.assertEqual(len(rewards['badges_unlocked']), 0)
        self.assertGreater(len(rewards['available_badges']), 0)
