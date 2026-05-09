from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import Wallet

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_wallet(sender, instance, created, **kwargs):
    if created:
        from apps.wallets.models import Wallet
        # Utiliser get_or_create au lieu de create évite le crash si le wallet existe déjà
        Wallet.objects.get_or_create(user=instance)