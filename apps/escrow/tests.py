from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.choices import EscrowStatus, MissionStatus
from apps.escrow.models import Escrow
from apps.escrow.services import EscrowService
from apps.missions.models import Mission
from apps.wallets.models import Wallet
from django.contrib.gis.geos import Point

User = get_user_model()


class EscrowFlowTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username='client1',
            email='client@test.com',
            phone_number='+22911111111',
            password='testpass123',
            is_client=True,
        )
        self.agent_user = User.objects.create_user(
            username='agent1',
            email='agent@test.com',
            phone_number='+22922222222',
            password='testpass123',
            is_agent=True,
        )
        self.client_wallet = Wallet.objects.create(
            user=self.client_user,
            balance=Decimal('50000.00'),
        )
        self.agent_wallet = Wallet.objects.create(
            user=self.agent_user,
            balance=Decimal('0.00'),
        )
        self.mission = Mission.objects.create(
            client=self.client_user,
            title='Test mission',
            description='Desc',
            location=Point(2.4, 6.3, srid=4326),
            address='Cotonou',
            price=Decimal('5000.00'),
            service_fee=Decimal('500.00'),
            purchase_amount=Decimal('1000.00'),
            service_amount=Decimal('5000.00'),
            status=MissionStatus.PENDING,
        )

    def test_lock_on_accept_moves_funds_to_escrow(self):
        self.mission.agent = self.agent_user
        self.mission.status = MissionStatus.ACCEPTED
        self.mission.save()

        EscrowService.lock_on_accept(self.mission)
        EscrowService.release_purchase_to_agent(self.mission)

        self.client_wallet.refresh_from_db()
        self.agent_wallet.refresh_from_db()
        escrow = Escrow.objects.get(mission=self.mission)

        self.assertEqual(escrow.status, EscrowStatus.HELD)
        self.assertEqual(escrow.amount, Decimal('5500.00'))
        self.assertEqual(self.client_wallet.escrow_balance, Decimal('5500.00'))
        self.assertEqual(self.agent_wallet.balance, Decimal('1000.00'))

    def test_release_to_agent_is_idempotent(self):
        self.mission.agent = self.agent_user
        self.mission.status = MissionStatus.ACCEPTED
        self.mission.save()
        EscrowService.lock_on_accept(self.mission)
        EscrowService.release_purchase_to_agent(self.mission)

        EscrowService.release_to_agent(self.mission)
        EscrowService.release_to_agent(self.mission)

        self.agent_wallet.refresh_from_db()
        self.assertEqual(self.agent_wallet.balance, Decimal('6500.00'))

    def test_insufficient_balance_raises(self):
        self.client_wallet.balance = Decimal('100.00')
        self.client_wallet.save()
        self.mission.agent = self.agent_user
        self.mission.save()

        with self.assertRaises(ValueError):
            EscrowService.lock_on_accept(self.mission)
