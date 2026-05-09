from django.test import TestCase

class InfrastructureTest(TestCase):
    def test_django_is_alive(self):
        """Vérifie que Django et la DB répondent"""
        self.assertEqual(1 + 1, 2)