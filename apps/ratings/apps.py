"""Configuration application ratings."""

from django.apps import AppConfig


class RatingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ratings'
    verbose_name = 'Notations'

    def ready(self):
        """Import signals when app is ready."""
        import apps.ratings.signals
