from django.db.models.signals import post_save
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from celery import shared_task

from .models import User
from apps.notifications.services import NotificationService
from apps.wallets.models import Wallet

User = get_user_model()

@shared_task
def send_welcome_email_task(user_id, user_email, username):
    """
    Tâche Celery asynchrone pour envoyer l'email de bienvenue
    """
    try:
        subject = 'Bienvenue sur FONACO !'
        message = f'''
        Bonjour {username},

        Bienvenue sur la plateforme FONACO !

        Nous sommes ravis de vous compter parmi nos utilisateurs. 
        FONACO vous permet de :
        • Devenir un Agent d'élite et proposer vos services
        • Déléguer vos tâches à des professionnels qualifiés
        • Accéder à une communauté active et engagée

        Votre compte est maintenant actif et prêt à être utilisé.

        Si vous avez des questions, n'hésitez pas à nous contacter.

        Cordialement,
        L'équipe FONACO
        Propulsé par IBIHUB BRIDGE

        ---
        Cet email a été généré automatiquement. Merci de ne pas y répondre.
        '''
        
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@fonaco.com'),
            recipient_list=[user_email],
            fail_silently=False,
        )
        
        print(f"Email de bienvenue envoyé à {user_email}")
        
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email de bienvenue: {e}")

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
        
        # Envoyer l'email de bienvenue de manière asynchrone via Celery
        try:
            send_welcome_email_task.delay(
                user_id=instance.id,
                user_email=instance.email,
                username=instance.get_full_name() or instance.username
            )
        except Exception as e:
            # Logger l'erreur mais ne pas bloquer la création de l'utilisateur
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erreur lors de l'envoi de l'email de bienvenue: {e}")
            print(f"DEBUG SIGNAL: Erreur email welcome - {e}")
        
        # Si parrainé, on peut envoyer une notification au parrain
        if instance.referred_by:
            # On pourrait ici verser un bonus de 500 FCFA par exemple
            pass            