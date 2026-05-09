from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class WalletsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.wallets'
    label = 'wallets'
    verbose_name = _("Gestion des Portefeuilles")

    def ready(self):
        import apps.wallets.signals