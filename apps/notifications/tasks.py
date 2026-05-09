from celery import shared_task
from firebase_admin import messaging
# Note : Il faudra faire 'pip install firebase-admin' plus tard

@shared_task
def send_fcm_notification(user_token, title, body, data=None):
    """Envoie une notification push via Firebase en arrière-plan"""
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=data or {},
        token=user_token,
    )
    try:
        response = messaging.send(message)
        return f"Successfully sent message: {response}"
    except Exception as e:
        return f"Failed to send message: {str(e)}"