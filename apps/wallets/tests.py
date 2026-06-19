from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.wallets.models import Wallet

User = get_user_model()


class WalletSignalTests(TestCase):
    def test_single_wallet_created_on_user_signup(self):
        user = User.objects.create_user(
            username='wallet_user',
            email='wallet@test.com',
            phone_number='+22933333333',
            password='testpass123',
            is_client=True,
        )
        self.assertEqual(Wallet.objects.filter(user=user).count(), 1)

    def test_get_or_create_wallet_is_idempotent(self):
        user = User.objects.create_user(
            username='wallet_user2',
            email='wallet2@test.com',
            phone_number='+22944444444',
            password='testpass123',
            is_client=True,
        )
        wallet, created = Wallet.objects.get_or_create(user=user)
        self.assertFalse(created)
        wallet2, created2 = Wallet.objects.get_or_create(user=user)
        self.assertFalse(created2)
        self.assertEqual(wallet.pk, wallet2.pk)
        self.assertEqual(Wallet.objects.filter(user=user).count(), 1)
