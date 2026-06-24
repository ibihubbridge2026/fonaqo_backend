"""Tests sécurité P0 + intégration Ledger."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.choices import MissionStatus
from apps.finance.models import LedgerEntry
from apps.missions.models import Mission
from apps.wallets.models import Wallet

User = get_user_model()


class DisputeIdorTest(TestCase):
    """AUDIT FIX [P0] — Un user ne peut pas ouvrir un litige sur la mission d'un autre."""

    def setUp(self):
        self.client = APIClient()
        self.client_user = User.objects.create_user(
            username='client1', email='client1@test.fonaqo.bj',
            password='Test1234!', is_client=True,
        )
        self.other_client = User.objects.create_user(
            username='client2', email='client2@test.fonaqo.bj',
            password='Test1234!', is_client=True,
        )
        self.agent = User.objects.create_user(
            username='agent1', email='agent1@test.fonaqo.bj',
            password='Test1234!', is_agent=True,
        )
        self.mission = Mission.objects.create(
            client=self.client_user,
            agent=self.agent,
            title='Mission test',
            description='Desc',
            location=Point(2.4, 6.4),
            address='Cotonou',
            price=Decimal('5000'),
        )
        self.client.force_authenticate(user=self.other_client)

    def test_non_participant_cannot_open_dispute(self):
        response = self.client.post(
            '/api/v1/disputes/',
            {
                'mission': self.mission.id,
                'title': 'Litige frauduleux',
                'description': 'Test IDOR',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        errors = response.data.get('errors', response.data)
        self.assertIn('mission', errors)


class WithdrawalPermissionTest(TestCase):
    """AUDIT FIX [P0] — Les clients ne peuvent pas retirer via payments/withdraw/."""

    def setUp(self):
        self.client = APIClient()
        self.client_user = User.objects.create_user(
            username='client_w', email='client_w@test.fonaqo.bj',
            password='Test1234!', is_client=True, is_agent=False,
        )
        self.agent_user = User.objects.create_user(
            username='agent_w', email='agent_w@test.fonaqo.bj',
            password='Test1234!', is_agent=True, is_client=False,
        )
        wallet, _ = Wallet.objects.get_or_create(user=self.client_user)
        wallet.balance = Decimal('10000')
        wallet.save()
        agent_wallet, _ = Wallet.objects.get_or_create(user=self.agent_user)
        agent_wallet.balance = Decimal('10000')
        agent_wallet.save()

    def test_client_withdrawal_blocked(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post(
            '/api/v1/payments/withdraw/',
            {'amount': '1000', 'channel': 'MTN_MOMO'},
            format='json',
        )
        self.assertIn(response.status_code, (403, 400))

    def test_agent_withdrawal_allowed(self):
        self.client.force_authenticate(user=self.agent_user)
        response = self.client.post(
            '/api/v1/payments/withdraw/',
            {'amount': '1000', 'channel': 'MTN_MOMO'},
            format='json',
        )
        self.assertIn(response.status_code, (201, 400))


class LedgerIntegrationTest(TestCase):
    """LedgerEntry créée lors d'un escrow lock."""

    def setUp(self):
        self.client_user = User.objects.create_user(
            username='client_l', email='client_l@test.fonaqo.bj',
            password='Test1234!', is_client=True,
        )
        self.agent_user = User.objects.create_user(
            username='agent_l', email='agent_l@test.fonaqo.bj',
            password='Test1234!', is_agent=True,
        )
        wallet, _ = Wallet.objects.get_or_create(user=self.client_user)
        wallet.balance = Decimal('20000')
        wallet.save()
        self.mission = Mission.objects.create(
            client=self.client_user,
            agent=self.agent_user,
            title='Mission ledger',
            description='Test',
            location=Point(2.4, 6.4),
            address='Cotonou',
            price=Decimal('5000'),
            status=MissionStatus.ACCEPTED,
        )

    def test_escrow_lock_creates_ledger_entry(self):
        from apps.escrow.services import EscrowService

        EscrowService.lock_on_accept(self.mission)
        self.assertTrue(
            LedgerEntry.objects.filter(
                entry_type='ESCROW_LOCK',
                mission_id=self.mission.id,
            ).exists(),
        )
