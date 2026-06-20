"""Tests pour l'assignation ciblée d'agents (target_agent_username)."""

from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import AgentProfile
from apps.core.choices import MissionStatus, AgentKYCStatus
from apps.missions.models import Mission
from apps.wallets.models import Wallet

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


def _get_auth_token(user):
    """Helper pour obtenir un token JWT."""
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


class TargetAgentAssignmentTest(TestCase):
    """Tests de l'assignation ciblée d'agents."""

    def setUp(self):
        self.client = APIClient()
        self.client_user = _make_user('client', is_client=True)
        self.target_agent = _make_user('john', is_agent=True)
        self.other_agent = _make_user('jane', is_agent=True)
        
        # Créer les AgentProfile avec KYC approved et agent_code unique
        AgentProfile.objects.create(
            user=self.target_agent,
            kyc_status=AgentKYCStatus.APPROVED,
            agent_code='AGT-00001'
        )
        AgentProfile.objects.create(
            user=self.other_agent,
            kyc_status=AgentKYCStatus.APPROVED,
            agent_code='AGT-00002'
        )

        # Créer wallet pour le client avec solde suffisant
        Wallet.objects.filter(user=self.client_user).delete()
        Wallet.objects.create(
            user=self.client_user,
            balance=Decimal('100000.00')
        )

        # Auth tokens
        self.target_agent_token = _get_auth_token(self.target_agent)
        self.other_agent_token = _get_auth_token(self.other_agent)
        self.client_token = _get_auth_token(self.client_user)

    @patch('apps.missions.views._agent_can_accept_more', return_value=True)
    @patch('apps.missions.views.EscrowService.lock_on_accept')
    def test_target_agent_can_accept(self, mock_escrow, mock_capacity):
        """L'agent ciblé peut accepter une mission qui lui est réservée."""
        mission = Mission.objects.create(
            client=self.client_user,
            target_agent_username='john',
            title='Test mission',
            description='Test',
            location=Point(2.4, 6.4),
            address='Cotonou',
            price=Decimal('5000'),
            status=MissionStatus.PENDING,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.target_agent_token}')
        response = self.client.post(f'/api/v1/missions/{mission.id}/accept/')

        self.assertEqual(response.status_code, 200)
        mission.refresh_from_db()
        self.assertEqual(mission.agent, self.target_agent)
        self.assertEqual(mission.status, MissionStatus.ACCEPTED)
        self.assertIsNone(mission.target_agent_username)  # Nettoyé après acceptation

    @patch('apps.missions.views._agent_can_accept_more', return_value=True)
    @patch('apps.missions.views.EscrowService.lock_on_accept')
    def test_other_agent_rejected(self, mock_escrow, mock_capacity):
        """Un autre agent ne peut pas accepter une mission réservée."""
        mission = Mission.objects.create(
            client=self.client_user,
            target_agent_username='john',
            title='Test mission',
            description='Test',
            location=Point(2.4, 6.4),
            address='Cotonou',
            price=Decimal('5000'),
            status=MissionStatus.PENDING,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.other_agent_token}')
        response = self.client.post(f'/api/v1/missions/{mission.id}/accept/')

        self.assertEqual(response.status_code, 403)
        self.assertIn('réservée', response.data['message'])
        mission.refresh_from_db()
        self.assertIsNone(mission.agent)
        self.assertEqual(mission.status, MissionStatus.PENDING)

    @patch('apps.missions.views._agent_can_accept_more', return_value=True)
    @patch('apps.missions.views.EscrowService.lock_on_accept')
    def test_public_mission_any_agent_can_accept(self, mock_escrow, mock_capacity):
        """Mission publique (target_agent_username=NULL) : tout agent peut accepter."""
        mission = Mission.objects.create(
            client=self.client_user,
            target_agent_username=None,
            title='Test mission',
            description='Test',
            location=Point(2.4, 6.4),
            address='Cotonou',
            price=Decimal('5000'),
            status=MissionStatus.PENDING,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.other_agent_token}')
        response = self.client.post(f'/api/v1/missions/{mission.id}/accept/')

        self.assertEqual(response.status_code, 200)
        mission.refresh_from_db()
        self.assertEqual(mission.agent, self.other_agent)

    def test_non_agent_cannot_accept(self):
        """Un client ne peut pas accepter une mission."""
        mission = Mission.objects.create(
            client=self.client_user,
            target_agent_username=None,
            title='Test mission',
            description='Test',
            location=Point(2.4, 6.4),
            address='Cotonou',
            price=Decimal('5000'),
            status=MissionStatus.PENDING,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.client_token}')
        response = self.client.post(f'/api/v1/missions/{mission.id}/accept/')

        self.assertEqual(response.status_code, 403)
        self.assertIn('agent', response.data['message'])

    @patch('apps.missions.views._agent_can_accept_more', return_value=True)
    @patch('apps.missions.views.EscrowService.lock_on_accept')
    def test_concurrent_accept_protection(self, mock_escrow, mock_capacity):
        """Protection contre l'acceptation simultanée par deux agents."""
        mission = Mission.objects.create(
            client=self.client_user,
            target_agent_username=None,
            title='Test mission',
            description='Test',
            location=Point(2.4, 6.4),
            address='Cotonou',
            price=Decimal('5000'),
            status=MissionStatus.PENDING,
        )

        # Premier agent accepte
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.target_agent_token}')
        response1 = self.client.post(f'/api/v1/missions/{mission.id}/accept/')

        # Deuxième agent tente d'accepter
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.other_agent_token}')
        response2 = self.client.post(f'/api/v1/missions/{mission.id}/accept/')

        # Une seule doit réussir (200), l'autre doit échouer (409)
        success_count = sum(1 for r in [response1, response2] if r.status_code == 200)
        conflict_count = sum(1 for r in [response1, response2] if r.status_code == 409)

        self.assertEqual(success_count, 1)
        self.assertEqual(conflict_count, 1)

        mission.refresh_from_db()
        self.assertIsNotNone(mission.agent)
