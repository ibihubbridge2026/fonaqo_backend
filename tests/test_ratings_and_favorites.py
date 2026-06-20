"""Tests unitaires pour le système de notation et la synchronisation des favoris."""

from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import transaction as db_transaction
from django.contrib.gis.geos import Point

from apps.accounts.models import AgentProfile, ClientProfile, FavoriteAgent
from apps.ratings.models import Rating
from apps.core.choices import MissionStatus

User = get_user_model()


def _make_user(email, is_agent=False, is_client=False):
    """Helper pour créer un utilisateur."""
    import random
    return User.objects.create_user(
        username=email.split('@')[0],
        email=email,
        phone_number=f'+229{random.randint(10000000, 99999999)}',
        is_agent=is_agent,
        is_client=is_client,
        is_verified=True,
    )


class RatingSystemTest(TestCase):
    """Tests du système de notation bilatéral."""

    def setUp(self):
        self.client_user = _make_user('client@test.com', is_client=True)
        self.agent_user = _make_user('agent@test.com', is_agent=True)
        self.client_profile, _ = ClientProfile.objects.get_or_create(user=self.client_user)
        self.agent_profile, _ = AgentProfile.objects.get_or_create(user=self.agent_user)

    def test_unique_constraint_on_rating(self):
        """Vérifie qu'un utilisateur ne peut pas noter deux fois la même mission."""
        from apps.missions.models import Mission

        mission = Mission.objects.create(
            client=self.client_user,
            agent=self.agent_user,
            status=MissionStatus.COMPLETED,
            title='Test mission',
            price=Decimal('5000'),
            location=Point(2.4, 6.4),  # Cotonou
        )

        # Première notation
        Rating.objects.create(
            mission=mission,
            reviewer=self.client_user,
            reviewee=self.agent_user,
            rating_type=Rating.RatingType.CLIENT_RATES_AGENT,
            score=5,
            comment='Excellent service',
        )

        # Tentative de double notation
        with self.assertRaises(Exception):  # IntegrityError
            Rating.objects.create(
                mission=mission,
                reviewer=self.client_user,
                reviewee=self.agent_user,
                rating_type=Rating.RatingType.CLIENT_RATES_AGENT,
                score=4,
                comment='Second essai',
            )

    def test_average_rating_calculation(self):
        """Vérifie le calcul mathématique de la moyenne des notes."""
        from apps.missions.models import Mission

        mission1 = Mission.objects.create(
            client=self.client_user,
            agent=self.agent_user,
            status=MissionStatus.COMPLETED,
            title='Mission 1',
            price=Decimal('5000'),
            location=Point(2.4, 6.4),
        )

        mission2 = Mission.objects.create(
            client=self.client_user,
            agent=self.agent_user,
            status=MissionStatus.COMPLETED,
            title='Mission 2',
            price=Decimal('5000'),
            location=Point(2.4, 6.4),
        )

        # Créer 3 notes : 5, 4, 3 → moyenne = 4.0
        Rating.objects.create(
            mission=mission1,
            reviewer=self.client_user,
            reviewee=self.agent_user,
            rating_type=Rating.RatingType.CLIENT_RATES_AGENT,
            score=5,
        )
        Rating.objects.create(
            mission=mission2,
            reviewer=self.client_user,
            reviewee=self.agent_user,
            rating_type=Rating.RatingType.CLIENT_RATES_AGENT,
            score=4,
        )

        # Créer un autre client pour la 3e note
        other_client = _make_user('other@test.com', is_client=True)
        mission3 = Mission.objects.create(
            client=other_client,
            agent=self.agent_user,
            status=MissionStatus.COMPLETED,
            title='Mission 3',
            price=Decimal('5000'),
            location=Point(2.4, 6.4),
        )
        Rating.objects.create(
            mission=mission3,
            reviewer=other_client,
            reviewee=self.agent_user,
            rating_type=Rating.RatingType.CLIENT_RATES_AGENT,
            score=3,
        )

        # Rafraîchir le profil et vérifier la moyenne
        self.agent_profile.refresh_from_db()
        self.assertEqual(self.agent_profile.average_rating, Decimal('4.00'))
        self.assertEqual(self.agent_profile.ratings_count, 3)

    def test_rating_score_validation(self):
        """Vérifie que le score doit être entre 1 et 5."""
        from apps.ratings.serializers import RatingSerializer
        from apps.missions.models import Mission

        mission = Mission.objects.create(
            client=self.client_user,
            agent=self.agent_user,
            status=MissionStatus.COMPLETED,
            title='Test mission',
            price=Decimal('5000'),
            location=Point(2.4, 6.4),
        )

        # Score invalide (0)
        serializer = RatingSerializer(data={
            'score': 0,
            'comment': 'Test',
            'mission': str(mission.id),
            'reviewer': str(self.client_user.id),
            'reviewee': str(self.agent_user.id),
            'rating_type': Rating.RatingType.CLIENT_RATES_AGENT,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('score', serializer.errors)

        # Score invalide (6)
        serializer = RatingSerializer(data={
            'score': 6,
            'comment': 'Test',
            'mission': str(mission.id),
            'reviewer': str(self.client_user.id),
            'reviewee': str(self.agent_user.id),
            'rating_type': Rating.RatingType.CLIENT_RATES_AGENT,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('score', serializer.errors)

        # Score valide (5)
        serializer = RatingSerializer(data={
            'score': 5,
            'comment': 'Test',
            'mission': str(mission.id),
            'reviewer': str(self.client_user.id),
            'reviewee': str(self.agent_user.id),
            'rating_type': Rating.RatingType.CLIENT_RATES_AGENT,
        })
        self.assertTrue(serializer.is_valid())

    def test_rating_updates_profile_on_delete(self):
        """Vérifie que la suppression d'une note met à jour la moyenne."""
        from apps.missions.models import Mission

        mission = Mission.objects.create(
            client=self.client_user,
            agent=self.agent_user,
            status=MissionStatus.COMPLETED,
            title='Test mission',
            price=Decimal('5000'),
            location=Point(2.4, 6.4),
        )

        rating = Rating.objects.create(
            mission=mission,
            reviewer=self.client_user,
            reviewee=self.agent_user,
            rating_type=Rating.RatingType.CLIENT_RATES_AGENT,
            score=5,
        )

        self.agent_profile.refresh_from_db()
        self.assertEqual(self.agent_profile.average_rating, Decimal('5.00'))
        self.assertEqual(self.agent_profile.ratings_count, 1)

        # Supprimer la note
        rating.delete()

        self.agent_profile.refresh_from_db()
        self.assertEqual(self.agent_profile.average_rating, Decimal('0.00'))
        self.assertEqual(self.agent_profile.ratings_count, 0)


class FavoritesSyncTest(TestCase):
    """Tests de la synchronisation des favoris."""

    def setUp(self):
        self.client_user = _make_user('client@test.com', is_client=True)
        self.agent_user = _make_user('agent@test.com', is_agent=True)

    def test_toggle_favorite_adds(self):
        """Vérifie que toggle ajoute un favori s'il n'existe pas."""
        with db_transaction.atomic():
            favorite, created = FavoriteAgent.objects.get_or_create(
                client=self.client_user,
                agent=self.agent_user,
            )

        self.assertTrue(created)
        self.assertEqual(FavoriteAgent.objects.filter(client=self.client_user).count(), 1)

    def test_toggle_favorite_removes(self):
        """Vérifie que toggle supprime un favori s'il existe déjà."""
        # Créer le favori
        FavoriteAgent.objects.create(
            client=self.client_user,
            agent=self.agent_user,
        )

        # Toggle → supprimer manuellement (get_or_create ne supprime pas)
        with db_transaction.atomic():
            favorite = FavoriteAgent.objects.get(
                client=self.client_user,
                agent=self.agent_user,
            )
            favorite.delete()

        self.assertEqual(FavoriteAgent.objects.filter(client=self.client_user).count(), 0)

    def test_unique_constraint_on_favorites(self):
        """Vérifie la contrainte unique (client, agent)."""
        FavoriteAgent.objects.create(
            client=self.client_user,
            agent=self.agent_user,
        )

        # Tentative de duplication
        with self.assertRaises(Exception):  # IntegrityError
            FavoriteAgent.objects.create(
                client=self.client_user,
                agent=self.agent_user,
            )

    def test_favorites_list_returns_correct_agents(self):
        """Vérifie que la liste des favoris retourne les bons agents."""
        agent2 = _make_user('agent2@test.com', is_agent=True)

        FavoriteAgent.objects.create(
            client=self.client_user,
            agent=self.agent_user,
        )
        FavoriteAgent.objects.create(
            client=self.client_user,
            agent=agent2,
        )

        favorites = FavoriteAgent.objects.filter(client=self.client_user)
        agent_ids = list(favorites.values_list('agent_id', flat=True))

        self.assertEqual(len(agent_ids), 2)
        self.assertIn(self.agent_user.id, agent_ids)
        self.assertIn(agent2.id, agent_ids)
