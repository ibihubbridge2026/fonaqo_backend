import logging

from fcm_django.models import FCMDevice
from firebase_admin import messaging

logger = logging.getLogger(__name__)


class NotificationService:
    @staticmethod
    def send_to_user(user, title, body, data=None):
        """
        Envoie une notification Push réelle via Firebase FCM.
        Utilise les devices enregistrés via FCMDevice (fcm-django).
        """
        devices = FCMDevice.objects.filter(user=user, active=True)

        if not devices.exists():
            logger.info(
                "Pas de device FCM pour %s. Notification ignorée: %s",
                user.username, title
            )
            return False

        try:
            result = devices.send_message(
                messaging.Message(
                    notification=messaging.Notification(
                        title=title,
                        body=body,
                    ),
                    data=data or {},
                )
            )
            logger.info("Notification envoyée à %s: %s", user.username, title)
            return True
        except Exception as e:
            logger.error("Erreur lors de l'envoi FCM à %s: %s", user.username, e)
            return False