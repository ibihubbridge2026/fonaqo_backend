from django.db.models.signals import post_save
from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import User
from apps.notifications.services import NotificationService
from apps.wallets.models import Wallet

@receiver(pre_save, sender=User)
def notify_agent_verification(sender, instance, **kwargs):
    # Si l'instance n'a pas de PK ou n'est pas encore en base, c'est une création
    if not instance.pk:
        return

    try:
        # On tente de récupérer l'ancienne version
        old_user = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        # L'utilisateur est en cours de création, donc pas de "old_user"
        return
    
    # Logique de vérification (is_verified passe de False à True)
    if not old_user.is_verified and instance.is_verified:
        NotificationService.send_to_user(
            user=instance,
            title="Compte vérifié ! 🚀",
            body="Félicitations, votre profil agent a été validé.",
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