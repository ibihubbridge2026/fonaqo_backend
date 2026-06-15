"""Tests healthcheck et routes staff (sans DB si indisponible)."""

from django.test import SimpleTestCase
from django.urls import reverse, resolve


class HealthRouteTests(SimpleTestCase):
    def test_health_route_resolves(self):
        match = resolve('/health/')
        self.assertEqual(match.url_name, 'health-check')

    def test_staff_kyc_queue_route_resolves(self):
        match = resolve('/api/v1/staff/kyc/queue/')
        self.assertEqual(match.url_name, 'staff-kyc-queue')


class WebSocketRoutingTests(SimpleTestCase):
    def test_websocket_patterns_registered(self):
        from apps.core.routing import websocket_urlpatterns

        self.assertGreaterEqual(len(websocket_urlpatterns), 2)
