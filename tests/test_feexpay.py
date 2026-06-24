"""Tests pour l'intégration FeexPay."""
import hashlib
import hmac
import json
from unittest.mock import patch

from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError

from apps.core.validators import validate_image_upload
from apps.payments.feexpay_service import FeexPayClient
from apps.payments.models import Payment
from apps.core.choices import PaymentStatus

User = get_user_model()


@override_settings(
    FEEXPAY_WEBHOOK_SECRET='test_webhook_secret',
    FEEXPAY_SANDBOX=True,
)
class FeexPayCallbackSecurityTest(TestCase):
    """AUDIT FIX [P0] — Tester la sécurité du callback."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='Test1234!')
        self.url = '/api/v1/payments/feexpay/callback/'

    def _make_signature(self, body: bytes) -> str:
        return hmac.new(
            b'test_webhook_secret', body, hashlib.sha256,
        ).hexdigest()

    def test_callback_rejects_missing_signature(self):
        """Un callback sans signature doit être rejeté (403) quand secret configuré."""
        response = self.client.post(
            self.url,
            data=json.dumps({'reference': 'TEST', 'status': 'SUCCESS'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_callback_rejects_invalid_signature(self):
        """Un callback avec une signature incorrecte doit être rejeté (403)."""
        body = json.dumps({'reference': 'TEST', 'status': 'SUCCESS'}).encode()
        response = self.client.post(
            self.url,
            data=body,
            content_type='application/json',
            HTTP_X_FEEXPAY_SIGNATURE='invalide',
        )
        self.assertEqual(response.status_code, 403)

    def test_callback_idempotency(self):
        """Un callback déjà crédité ne doit PAS re-créditer."""
        payment = Payment.objects.create(
            user=self.user,
            amount=5000,
            status=PaymentStatus.SUCCESS,
            external_reference='FNQ-TEST001',
            provider_transaction_id='feex-123',
        )
        body = json.dumps({
            'reference': 'FNQ-TEST001',
            'status': 'SUCCESS',
            'transaction_id': 'feex-123',
        }).encode()
        sig = self._make_signature(body)

        with patch('apps.payments.services.FeexPayService.apply_success') as mock_apply:
            response = self.client.post(
                self.url,
                data=body,
                content_type='application/json',
                HTTP_X_FEEXPAY_SIGNATURE=sig,
            )

        self.assertEqual(response.status_code, 200)
        mock_apply.assert_not_called()


class FeexPayClientTest(TestCase):
    def test_generate_reference_unique(self):
        ref1 = FeexPayClient.generate_reference('DEP')
        ref2 = FeexPayClient.generate_reference('DEP')
        self.assertNotEqual(ref1, ref2)
        self.assertTrue(ref1.startswith('DEP-'))


class FeexPayUploadValidationTest(TestCase):
    """AUDIT FIX [P0] — Tester la validation des uploads."""

    def test_reject_php_file_as_image(self):
        """Un fichier PHP déguisé en image doit être rejeté."""
        fake_php = SimpleUploadedFile(
            'evil.php',
            b"<?php system($_GET['cmd']); ?>",
            content_type='image/jpeg',
        )
        with self.assertRaises(ValidationError):
            validate_image_upload(fake_php)
