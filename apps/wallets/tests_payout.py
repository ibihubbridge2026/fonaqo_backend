from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.choices import PayoutRequestStatus, TransactionStatus
from apps.core.models import AdminAuditLog
from apps.wallets.models import PayoutRequest, Transaction, Wallet
from apps.wallets.payout_service import PayoutService, PayoutServiceError

User = get_user_model()


class PayoutRequestFlowTests(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user(
            username='payout_agent',
            email='payout_agent@test.com',
            phone_number='+22961111111',
            password='testpass123',
            is_agent=True,
        )
        self.staff = User.objects.create_user(
            username='payout_admin',
            email='admin_payout@test.com',
            phone_number='+22962222222',
            password='testpass123',
            is_staff=True,
        )
        self.wallet = Wallet.objects.get(user=self.agent)
        self.wallet.balance = Decimal('10000')
        self.wallet.save()

    def test_request_does_not_debit_wallet(self):
        payout = PayoutService.request_withdrawal(
            wallet=self.wallet,
            amount=Decimal('3000'),
            payment_method='MTN',
            phone_number='+22961111111',
        )
        self.wallet.refresh_from_db()
        self.assertEqual(payout.status, PayoutRequestStatus.PENDING)
        self.assertEqual(self.wallet.balance, Decimal('10000'))

    def test_approve_creates_completed_withdrawal(self):
        payout = PayoutService.request_withdrawal(
            wallet=self.wallet,
            amount=Decimal('4000'),
            payment_method='MTN',
            phone_number='+22961111111',
        )
        approved = PayoutService.approve(payout, admin_user=self.staff)
        self.wallet.refresh_from_db()

        self.assertEqual(approved.status, PayoutRequestStatus.COMPLETED)
        self.assertEqual(self.wallet.balance, Decimal('6000'))
        self.assertIsNotNone(approved.ledger_transaction)
        self.assertEqual(
            approved.ledger_transaction.transaction_type,
            Transaction.TransactionType.WITHDRAWAL,
        )
        self.assertEqual(
            approved.ledger_transaction.status,
            TransactionStatus.COMPLETED,
        )

    def test_reject_does_not_debit(self):
        payout = PayoutService.request_withdrawal(
            wallet=self.wallet,
            amount=Decimal('2000'),
            payment_method='MOOV',
            phone_number='+22961111111',
        )
        rejected = PayoutService.reject(
            payout, admin_user=self.staff, reason='Test',
        )
        self.wallet.refresh_from_db()

        self.assertEqual(rejected.status, PayoutRequestStatus.REJECTED)
        self.assertEqual(self.wallet.balance, Decimal('10000'))
        self.assertFalse(
            Transaction.objects.filter(
                wallet=self.wallet,
                transaction_type=Transaction.TransactionType.WITHDRAWAL,
            ).exists(),
        )

    def test_double_approve_returns_400(self):
        payout = PayoutService.request_withdrawal(
            wallet=self.wallet,
            amount=Decimal('1000'),
            payment_method='MTN',
            phone_number='+22961111111',
        )
        PayoutService.approve(payout, admin_user=self.staff)

        client = APIClient()
        client.force_authenticate(user=self.staff)
        res = client.post(f'/api/v1/staff/payouts/{payout.id}/approve/')
        self.assertEqual(res.status_code, 400)

    def test_staff_approve_logs_audit(self):
        payout = PayoutService.request_withdrawal(
            wallet=self.wallet,
            amount=Decimal('1500'),
            payment_method='MTN',
            phone_number='+22961111111',
        )
        client = APIClient()
        client.force_authenticate(user=self.staff)
        res = client.post(f'/api/v1/staff/payouts/{payout.id}/approve/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(
            AdminAuditLog.objects.filter(
                action='PAYOUT_APPROVE',
                target_type='PayoutRequest',
            ).exists(),
        )
