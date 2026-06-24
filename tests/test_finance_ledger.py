"""Tests ledger : immutabilité, rapprochement, API staff."""
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.admin_alert_service import notify_staff
from apps.core.models import AdminNotification
from apps.core.choices import EscrowStatus, MissionStatus
from apps.escrow.models import Escrow
from apps.finance.exceptions import ImmutableLedgerError
from apps.finance.ledger_service import LedgerService
from apps.finance.models import LedgerEntry, LedgerEntryType, LedgerReconciliationRun
from apps.finance.reconciliation import run_reconciliation
from apps.missions.models import Mission
from apps.wallets.models import Wallet

User = get_user_model()


class LedgerImmutabilityTest(TestCase):
    def test_update_forbidden(self):
        entry = LedgerService.record_entry(
            entry_type=LedgerEntryType.WALLET_DEPOSIT,
            debit_account='wallet:test',
            credit_account='external:deposit',
            amount=Decimal('1000'),
            reference=f'LEDGER-TEST-{uuid4()}',
            description='Test immutabilité',
        )
        entry.description = 'modifié'
        with self.assertRaises(ImmutableLedgerError):
            entry.save()

    def test_delete_forbidden(self):
        entry = LedgerService.record_entry(
            entry_type=LedgerEntryType.WALLET_DEPOSIT,
            debit_account='wallet:test2',
            credit_account='external:deposit',
            amount=Decimal('500'),
            reference=f'LEDGER-TEST-{uuid4()}',
            description='Test delete',
        )
        with self.assertRaises(ImmutableLedgerError):
            entry.delete()

    def test_bulk_update_forbidden(self):
        LedgerService.record_entry(
            entry_type=LedgerEntryType.WALLET_DEPOSIT,
            debit_account='wallet:bulk',
            credit_account='external:deposit',
            amount=Decimal('100'),
            reference=f'LEDGER-BULK-{uuid4()}',
            description='Bulk test',
        )
        with self.assertRaises(ImmutableLedgerError):
            LedgerEntry.objects.filter(debit_account='wallet:bulk').update(amount=0)


class LedgerReconciliationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='recon_user',
            email='recon@test.fonaqo.bj',
            password='Test1234!',
            is_client=True,
        )
        self.wallet, _ = Wallet.objects.get_or_create(user=self.user)
        self.wallet.balance = Decimal('10000')
        self.wallet.escrow_balance = Decimal('2000')
        self.wallet.save()

    def test_reconciliation_ok_when_ledger_matches(self):
        LedgerService.record_entry(
            entry_type=LedgerEntryType.FEEXPAY_DEPOSIT,
            debit_account=f'wallet:{self.user.id}',
            credit_account='external:feexpay',
            amount=Decimal('10000'),
            reference=f'LEDGER-RECON-{uuid4()}',
            user_id=self.user.id,
            description='Dépôt test',
        )
        LedgerService.record_entry(
            entry_type=LedgerEntryType.ESCROW_LOCK,
            debit_account=f'escrow:{self.user.id}',
            credit_account=f'wallet:{self.user.id}',
            amount=Decimal('2000'),
            reference=f'LEDGER-ESCROW-{uuid4()}',
            user_id=self.user.id,
            description='Séquestre test',
        )
        # Aligner le wallet opérationnel sur le ledger (10000 dépôt - 2000 séquestre)
        self.wallet.balance = Decimal('8000')
        self.wallet.escrow_balance = Decimal('2000')
        self.wallet.save()

        run = run_reconciliation(notify_on_mismatch=False)
        self.assertEqual(run.status, LedgerReconciliationRun.Status.OK)
        self.assertEqual(run.mismatches_count, 0)

    def test_reconciliation_detects_mismatch(self):
        run = run_reconciliation(notify_on_mismatch=False)
        self.assertEqual(run.status, LedgerReconciliationRun.Status.MISMATCH)
        self.assertGreater(run.mismatches_count, 0)


class StaffLedgerApiTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='admin_ledger',
            email='admin@test.fonaqo.bj',
            password='Admin1234!',
        )
        self.regular = User.objects.create_user(
            username='user_ledger',
            email='user@test.fonaqo.bj',
            password='Test1234!',
        )
        LedgerService.record_entry(
            entry_type=LedgerEntryType.WALLET_DEPOSIT,
            debit_account='wallet:staff',
            credit_account='external:deposit',
            amount=Decimal('3000'),
            reference=f'LEDGER-STAFF-{uuid4()}',
            description='Entrée staff test',
        )

    def test_staff_ledger_requires_admin(self):
        self.client.force_authenticate(user=self.regular)
        response = self.client.get('/api/v1/staff/ledger/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_ledger_list_admin(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/staff/ledger/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_staff_ledger_export_csv(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/staff/ledger/export/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn('entry_type', response.content.decode())

    def test_staff_ledger_search(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/staff/ledger/', {'q': 'staff test'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)


class MaterialReleaseLedgerTest(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username='client_mat', email='client_mat@test.fonaqo.bj',
            password='Test1234!', is_client=True,
        )
        self.agent_user = User.objects.create_user(
            username='agent_mat', email='agent_mat@test.fonaqo.bj',
            password='Test1234!', is_agent=True,
        )
        wallet, _ = Wallet.objects.get_or_create(user=self.client_user)
        wallet.balance = Decimal('0')
        wallet.escrow_balance = Decimal('3000')
        wallet.save()
        self.mission = Mission.objects.create(
            client=self.client_user,
            agent=self.agent_user,
            title='Mission matériel',
            description='Test',
            location=Point(2.4, 6.4),
            address='Cotonou',
            price=Decimal('5000'),
            material_cost=Decimal('1500'),
            status=MissionStatus.ACCEPTED,
        )
        Escrow.objects.create(
            mission=self.mission,
            amount=Decimal('3000'),
            status=EscrowStatus.HELD,
        )

    def test_release_material_creates_ledger_entry(self):
        from apps.escrow.services import EscrowService

        EscrowService.release_material_to_agent(self.mission)
        self.assertTrue(
            LedgerEntry.objects.filter(
                entry_type='MISSION_PAYMENT',
                mission_id=self.mission.id,
                reference__startswith='LEDGER-MATERIAL-',
            ).exists(),
        )


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    ADMIN_ALERT_EMAILS=['ops@fonaco.com'],
)
class AdminNotificationAlertTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='admin_notify',
            email='admin_notify@test.fonaqo.bj',
            password='Admin1234!',
        )

    def test_notify_staff_stores_and_emails(self):
        notify_staff(
            category=AdminNotification.Category.SYSTEM,
            severity=AdminNotification.Severity.CRITICAL,
            title='Test alerte',
            message='Corps du message test',
        )
        self.assertEqual(AdminNotification.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Test alerte', mail.outbox[0].subject)

    def test_staff_notifications_api(self):
        AdminNotification.objects.create(
            category=AdminNotification.Category.SYSTEM,
            severity=AdminNotification.Severity.CRITICAL,
            title='Alerte visible',
            message='Doit apparaître dans l API',
        )
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/staff/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['unread_count'], 1)
        self.assertEqual(response.data['results'][0]['title'], 'Alerte visible')
