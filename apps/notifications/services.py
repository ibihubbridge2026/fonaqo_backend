from firebase_admin import messaging
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def send_to_user(user, title, body, data=None):
        """
        Envoie une notification Push réelle via Firebase FCM.
        """
        # On vérifie si l'utilisateur a un token FCM (enregistré via le mobile)
        # Tu devras ajouter un champ 'fcm_token' à ton modèle User si ce n'est pas fait
        if not hasattr(user, 'fcm_token') or not user.fcm_token:
            print(f"Pas de token FCM pour {user.username}. Notification console uniquement.")
            print(f"[SIMULATION] {title}: {body}")
            return False

        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=user.fcm_token,
        )

        try:
            response = messaging.send(message)
            print(f"Notification envoyée avec succès: {response}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi FCM: {e}")
            return False