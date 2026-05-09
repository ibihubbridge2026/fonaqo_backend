from django.apps import AppConfig


class EscrowConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.escrow'
    label = 'escrow'

    def ready(self):
        import apps.escrow.signals
