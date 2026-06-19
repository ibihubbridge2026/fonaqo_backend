import logging
import smtplib

logger = logging.getLogger(__name__)

from django.db.models.signals import post_save
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from celery import shared_task

from .models import User
from apps.notifications.services import NotificationService

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
        
        logger.info(f"Email de bienvenue envoyé à {user_email}")
        
    except (smtplib.SMTPException, ConnectionError, TimeoutError) as e:
        logger.error(f"Erreur lors de l'envoi de l'email de bienvenue: {e}")

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
def send_welcome_email_on_signup(sender, instance, created, **kwargs):
    """Portefeuille créé par apps.wallets.signals — pas de doublon ici."""
    if not created or getattr(instance, 'is_guest', False):
        return

    try:
        send_welcome_email_task.apply_async(
            kwargs={
                'user_id': str(instance.id),
                'user_email': instance.email,
                'username': instance.get_full_name() or instance.username,
            },
            ignore_result=True,
        )
    except Exception:
        logger.warning("Impossible d'envoyer l'email de bienvenue (Celery indisponible)")

    if instance.referred_by:
        pass