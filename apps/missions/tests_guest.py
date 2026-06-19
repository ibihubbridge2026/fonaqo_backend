from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.missions.guest_service import GuestLaborEstimator, GuestTrackingCodeGenerator

User = get_user_model()


class GuestModeTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_labor_estimator(self):
        low = GuestLaborEstimator.estimate('court')
        high = GuestLaborEstimator.estimate('x' * 500)
        self.assertGreaterEqual(low, Decimal('3500'))
        self.assertLessEqual(high, Decimal('150000'))

    def test_tracking_code_unique_format(self):
        code = GuestTrackingCodeGenerator.generate()
        self.assertTrue(code.startswith('FNC-'))
        self.assertTrue(code.endswith('-BJ'))

    def test_guest_create_endpoint(self):
        res = self.client.post(
            '/api/v1/public/missions/guest-create/',
            {
                'email': 'guest@test.fonaco.local',
                'phone': '+22997000099',
                'description': 'Réparation plomberie urgente sous évier cuisine',
                'address': 'Cotonou, Akpakpa',
                'latitude': 6.37,
                'longitude': 2.39,
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        payload = res.json().get('data', res.json())
        self.assertIn('tracking_code', payload)
        self.assertIn('payment_id', payload)
        user = User.objects.get(email='guest@test.fonaco.local')
        self.assertTrue(user.is_guest)

    def test_public_track_by_tracking_code(self):
        create = self.client.post(
            '/api/v1/public/missions/guest-create/',
            {
                'email': 'track@test.fonaco.local',
                'phone': '+22997000098',
                'description': 'Mission test suivi public',
                'address': 'Porto-Novo centre',
            },
            format='json',
        )
        code = create.json().get('data', create.json())['tracking_code']
        track = self.client.get(f'/api/v1/public/mission-track/?reference={code}')
        self.assertEqual(track.status_code, 200)
        body = track.json().get('data', track.json())
        self.assertTrue(body['found'])
        self.assertEqual(body['mission']['tracking_code'], code)
