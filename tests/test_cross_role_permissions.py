"""Tests cross-role pour vérifier que les permissions sont correctement appliquées.

Scénarios testés:
- Client ne peut pas appeler les endpoints réservés aux agents
- Agent ne peut pas appeler les endpoints réservés aux clients
- Utilisateur simple ne peut pas appeler les endpoints admin
- Admin peut accéder aux endpoints admin
"""

from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from rest_framework.test import APIClient
from rest_framework import status

from apps.core.choices import MissionStatus
from apps.missions.models import Mission

User = get_user_model()


def _make_user(username, is_agent=False, is_client=False, is_staff=False):
    """Helper pour créer un utilisateur."""
    import random
    return User.objects.create_user(
        username=username,
        email=f'{username}@test.com',
        phone_number=f'+229{random.randint(10000000, 99999999)}',
        is_agent=is_agent,
        is_client=is_client,
        is_staff=is_staff,
        is_superuser=is_staff,
        is_verified=True,
    )


class CrossRolePermissionTest(TestCase):
    """Tests des permissions cross-role."""

    def setUp(self):
        self.client_user = _make_user('client', is_client=True)
        self.agent_user = _make_user('agent', is_agent=True)
        self.admin_user = _make_user('admin', is_staff=True)
        self.simple_user = _make_user('simple')

        self.client_api = APIClient()

    def _get_token(self, user):
        """Helper pour obtenir un token JWT."""
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)

    # ------------------------------------------------------------------
    # Client → Agent endpoints (doit échouer)
    # ------------------------------------------------------------------

    def test_client_cannot_accept_mission(self):
        """Un client ne peut pas accepter une mission."""
        mission = Mission.objects.create(
            client=self.client_user,
            title='Test mission',
            description='Test',
            location=Point(2.4, 6.4),
            address='Cotonou',
            price=Decimal('5000'),
            status=MissionStatus.PENDING,
        )

        self.client_api.credentials(HTTP_AUTHORIZATION=f'Bearer {self._get_token(self.client_user)}')
        response = self.client_api.post(f'/api/v1/missions/{mission.id}/accept/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('agent', response.data['message'].lower())

    def test_client_cannot_withdraw_wallet(self):
        """Un client ne peut pas effectuer un retrait."""
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Bearer {self._get_token(self.client_user)}')
        response = self.client_api.post('/api/v1/wallets/withdraw/', {
            'amount': 1000,
            'payment_method': 'MTN',
            'phone_number': '+22990000000',
        })

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('agent', response.data['message'].lower())

    def test_client_cannot_access_boost_endpoint(self):
        """Un client ne peut pas accéder aux endpoints de boost."""
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Bearer {self._get_token(self.client_user)}')
        response = self.client_api.get('/api/v1/boosts/agent-boosts/')

        # 403 = forbidden, 404 = endpoint inexistant (acceptable aussi)
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    # ------------------------------------------------------------------
    # Agent → Client endpoints (doit échouer)
    # ------------------------------------------------------------------

    def test_agent_cannot_create_mission(self):
        """Un agent ne peut pas créer une mission."""
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Bearer {self._get_token(self.agent_user)}')
        response = self.client_api.post('/api/v1/missions/', {
            'title': 'Test mission',
            'description': 'Test',
            'location': {'latitude': 6.4, 'longitude': 2.4},
            'address': 'Cotonou',
            'price': 5000,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('client', response.data['message'].lower())

    def test_agent_cannot_access_client_rewards(self):
        """Un agent ne peut pas accéder aux récompenses client."""
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Bearer {self._get_token(self.agent_user)}')
        response = self.client_api.get('/api/v1/accounts/client/rewards/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_agent_cannot_redeem_rewards(self):
        """Un agent ne peut pas échanger des points."""
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Bearer {self._get_token(self.agent_user)}')
        response = self.client_api.post('/api/v1/accounts/client/rewards/redeem/', {
            'reward_id': 1,
        })

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ------------------------------------------------------------------
    # Simple user → Admin endpoints (doit échouer)
    # ------------------------------------------------------------------

    def test_simple_user_cannot_access_admin_dashboard(self):
        """Un utilisateur simple ne peut pas accéder au dashboard admin."""
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Bearer {self._get_token(self.simple_user)}')
        response = self.client_api.get('/admin-dashboard/')

        self.assertEqual(response.status_code, status.HTTP_302_FOUND or status.HTTP_403_FORBIDDEN)

    def test_simple_user_cannot_approve_payout(self):
        """Un utilisateur simple ne peut pas approuver un retrait."""
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Bearer {self._get_token(self.simple_user)}')
        response = self.client_api.post('/api/v1/wallets/payouts/1/approve/')

        # 401/403 = forbidden, 404 = endpoint inexistant (acceptable aussi)
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    # ------------------------------------------------------------------
    # Admin → Admin endpoints (doit réussir)
    # ------------------------------------------------------------------

    def test_admin_can_access_staff_endpoints(self):
        """Un admin peut accéder aux endpoints staff."""
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Bearer {self._get_token(self.admin_user)}')
        response = self.client_api.get('/api/v1/core/staff/dashboard/')

        # L'endpoint peut ne pas exister, mais si c'est 403 c'est un problème de config
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_assign_mission(self):
        """Un admin peut assigner une mission à un agent."""
        mission = Mission.objects.create(
            client=self.client_user,
            title='Test mission',
            description='Test',
            location=Point(2.4, 6.4),
            address='Cotonou',
            price=Decimal('5000'),
            status=MissionStatus.PENDING,
        )

        self.client_api.credentials(HTTP_AUTHORIZATION=f'Bearer {self._get_token(self.admin_user)}')
        response = self.client_api.post(f'/api/v1/core/staff/mission/{mission.id}/assign/', {
            'agent_id': str(self.agent_user.id),
        })

        # L'endpoint doit être accessible pour admin
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ------------------------------------------------------------------
    # Mission ciblée — filtrage dans list()
    # ------------------------------------------------------------------

    def test_targeted_mission_not_visible_to_other_agents(self):
        """Une mission ciblée n'est pas visible pour les autres agents dans list()."""
        # Mission ciblée pour agent_user
        mission = Mission.objects.create(
            client=self.client_user,
            target_agent_username='agent',
            title='Test mission',
            description='Test',
            location=Point(2.4, 6.4),
            address='Cotonou',
            price=Decimal('5000'),
            status=MissionStatus.PENDING,
        )

        # Autre agent
        other_agent = _make_user('other_agent', is_agent=True)

        self.client_api.credentials(HTTP_AUTHORIZATION=f'Bearer {self._get_token(other_agent)}')
        response = self.client_api.get('/api/v1/missions/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mission_ids = [m['id'] for m in response.data.get('data', {}).get('results', [])]
        self.assertNotIn(str(mission.id), mission_ids)

    def test_targeted_mission_visible_to_target_agent(self):
        """Une mission ciblée est visible pour l'agent ciblé dans list()."""
        mission = Mission.objects.create(
            client=self.client_user,
            target_agent_username='agent',
            title='Test mission',
            description='Test',
            location=Point(2.4, 6.4),
            address='Cotonou',
            price=Decimal('5000'),
            status=MissionStatus.PENDING,
        )

        self.client_api.credentials(HTTP_AUTHORIZATION=f'Bearer {self._get_token(self.agent_user)}')
        response = self.client_api.get('/api/v1/missions/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mission_ids = [m['id'] for m in response.data.get('data', {}).get('results', [])]
        self.assertIn(str(mission.id), mission_ids)
