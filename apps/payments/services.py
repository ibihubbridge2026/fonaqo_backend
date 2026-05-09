import requests
from django.conf import settings
from .models import Payment

class FeexPayService:
    BASE_URL = "https://api.feexpay.me/backend" # À vérifier selon leur doc actuelle

    @staticmethod
    def init_payment(user, amount, callback_url):
        # 1. Créer l'enregistrement local
        payment = Payment.objects.create(
            user=user,
            amount=amount,
            status=Payment.PaymentStatus.PENDING
        )

        # 2. Préparer la requête pour FeexPay
        payload = {
            "amount": int(amount),
            "currency": "XOF",
            "description": f"Rechargement Wallet Queue-Master - {user.phone_number}",
            "callback_url": callback_url,
            "external_id": str(payment.id),
            "token": settings.FEEXPAY_API_KEY # À configurer dans settings
        }

        # 3. Appel API (C'est un exemple de structure, à adapter à leur SDK/API)
        # response = requests.post(f"{FeexPayService.BASE_URL}/v1/transaction/init", json=payload)
        # return response.json()
        return payment