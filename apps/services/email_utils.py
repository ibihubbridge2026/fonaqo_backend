"""
Utilitaires d'envoi d'emails pour FONACO
Utilise Django send_mail avec configuration MailDev en développement
"""
import logging
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_welcome_email(user_email, user_name):
    """
    Envoie un email de bienvenue après inscription
    
    Args:
        user_email (str): Email de l'utilisateur
        user_name (str): Nom de l'utilisateur
    
    Returns:
        bool: True si envoyé avec succès, False sinon
    """
    try:
        subject = 'Bienvenue sur FONACO !'
        
        # Message texte simple (pas de template HTML pour l'instant)
        message = f"""
Bonjour {user_name},

Bienvenue sur la plateforme FONACO !

Nous sommes ravis de vous accueillir dans notre communauté de services.
Vous pouvez maintenant :
- Créer des missions en tant que client
- Proposer vos services en tant qu'agent
- Bénéficier de notre système de paiement sécurisé

Si vous avez des questions, n'hésitez pas à nous contacter.

Cordialement,
L'équipe FONACO
        """.strip()
        
        # Envoi de l'email
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
        
        logger.info(f"Email de bienvenue envoyé à {user_email}")
        return True
        
    except Exception as e:
        logger.error(f"Erreur envoi email de bienvenue à {user_email}: {str(e)}")
        return False


def send_password_reset_email(user_email, reset_code):
    """
    Envoie un email de réinitialisation de mot de passe
    
    Args:
        user_email (str): Email de l'utilisateur
        reset_code (str): Code de réinitialisation
    
    Returns:
        bool: True si envoyé avec succès, False sinon
    """
    try:
        subject = 'Réinitialisation de votre mot de passe FONACO'
        
        message = f"""
Bonjour,

Vous avez demandé la réinitialisation de votre mot de passe sur FONACO.

Voici votre code de réinitialisation : {reset_code}

Ce code est valable pendant 24 heures.

Si vous n'avez pas fait cette demande, vous pouvez ignorer cet email.

Cordialement,
L'équipe FONACO
        """.strip()
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
        
        logger.info(f"Email de réinitialisation envoyé à {user_email}")
        return True
        
    except Exception as e:
        logger.error(f"Erreur envoi email de réinitialisation à {user_email}: {str(e)}")
        return False


def is_maildev_available():
    """
    Vérifie si MailDev est disponible (test simple)
    
    Returns:
        bool: True si MailDev semble disponible, False sinon
    """
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)  # Timeout de 2 secondes
        result = sock.connect_ex(('localhost', 1025))
        sock.close()
        return result == 0
    except Exception:
        return False


def log_email_status():
    """
    Log l'état du service email pour le debugging
    """
    maildev_available = is_maildev_available()
    logger.info(f"Configuration Email: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
    logger.info(f"MailDev disponible: {maildev_available}")
    logger.info(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    
    return maildev_available
