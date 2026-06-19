from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import AdminAuditLog, PlatformConfiguration
from apps.core.services import FEES_URGENT_KEY

User = get_user_model()


class StaffAPITestCase(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='admin_staff',
            email='admin@fonaco.test',
            phone_number='+22960000001',
            password='testpass123',
            is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.staff)
        PlatformConfiguration.objects.get_or_create(
            key=FEES_URGENT_KEY,
            defaults={'value': '500'},
        )

    def test_dashboard_kpis(self):
        res = self.client.get('/api/v1/staff/dashboard/kpis/')
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        data = payload.get('data', payload)
        self.assertIn('volume_escrow', data)
        self.assertIn('revenue_split', data)

    def test_dashboard_activity(self):
        res = self.client.get('/api/v1/staff/dashboard/activity/')
        self.assertEqual(res.status_code, 200)
        data = res.json().get('data', res.json())
        self.assertIn('results', data)

    def test_dashboard_recent_missions(self):
        res = self.client.get('/api/v1/staff/dashboard/recent-missions/')
        self.assertEqual(res.status_code, 200)
        data = res.json().get('data', res.json())
        self.assertIn('results', data)

    def test_platform_config_patch(self):
        res = self.client.patch(
            '/api/v1/staff/platform-config/',
            {'FEES_URGENT': '750'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(
            AdminAuditLog.objects.filter(action='PLATFORM_CONFIG_PATCH').exists(),
        )

    def test_audit_log_empty(self):
        res = self.client.get('/api/v1/staff/audit-log/')
        self.assertEqual(res.status_code, 200)
        payload = res.json().get('data', res.json())
        self.assertIn('results', payload)

    def test_payouts_pending(self):
        res = self.client.get('/api/v1/staff/payouts/pending/')
        self.assertEqual(res.status_code, 200)

    def test_non_staff_forbidden(self):
        agent = User.objects.create_user(
            username='agent1',
            email='agent@fonaco.test',
            phone_number='+22960000002',
            password='testpass123',
            is_agent=True,
        )
        anon = APIClient()
        anon.force_authenticate(user=agent)
        res = anon.get('/api/v1/staff/dashboard/kpis/')
        self.assertEqual(res.status_code, 403)
