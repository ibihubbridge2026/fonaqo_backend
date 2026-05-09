from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import User
from apps.notifications.services import NotificationService
from apps.wallets.models import Wallet

@receiver(pre_save, sender=User)
def notify_agent_verification(sender, instance, **kwargs):
    if instance.pk:
        # On récupère la version actuelle en base de données avant la sauvegarde
        old_user = User.objects.get(pk=instance.pk)
        
        # Si is_verified passe de False à True
        if not old_user.is_verified and instance.is_verified:
            NotificationService.send_to_user(
                user=instance,
                title="Compte vérifié ! 🎉",
                body="Félicitations, votre profil agent a été validé. Vous pouvez dès maintenant accepter des missions.",
                data={"type": "KYC_SUCCESS"}
            )

@receiver(post_save, sender=User)
def create_user_wallet_and_referral(sender, instance, created, **kwargs):
    if created:
        # Créer le wallet automatiquement à l'inscription
        Wallet.objects.get_or_create(user=instance)
        
        # Si parrainé, on peut envoyer une notification au parrain
        if instance.referred_by:
            # On pourrait ici verser un bonus de 500 FCFA par exemple
            pass            