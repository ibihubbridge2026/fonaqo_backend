"""
Service FeexPay — Intégration Mobile Money + Carte
AUDIT FIX [P0] — Sécurisation callback avec HMAC + idempotency
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from decimal import Decimal

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class FeexPayClient:
    """Client HTTP bas niveau pour l'API FeexPay."""

    BASE_URL = "https://api.feexpay.me"

    def __init__(self):
        self.shop_id = getattr(settings, "FEEXPAY_SHOP_ID", "")
        self.token = getattr(settings, "FEEXPAY_API_TOKEN", "") or getattr(
            settings, "FEEXPAY_API_KEY", ""
        )
        self.mode = getattr(settings, "FEEXPAY_MODE", "SANDBOX")
        self.callback_base = getattr(settings, "FEEXPAY_CALLBACK_BASE_URL", "") or getattr(
            settings, "FEEXPAY_CALLBACK_URL", "http://localhost:8000"
        )
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def initiate_mobile_payment(
        self,
        amount: Decimal,
        phone_number: str,
        network: str,
        full_name: str,
        email: str,
        reference: str,
        description: str = "",
    ) -> dict:
        """Initier un paiement Mobile Money via FeexPay."""
        callback_url = f"{self.callback_base.rstrip('/')}/api/v1/payments/feexpay/callback/"

        parts = (full_name or "").split()
        payload = {
            "shop": self.shop_id,
            "amount": int(amount),
            "phone_number": phone_number,
            "network": network.upper(),
            "firstname": parts[0] if parts else "",
            "lastname": " ".join(parts[1:]) if len(parts) > 1 else "",
            "email": email,
            "reference": reference,
            "description": description or f"Paiement FONAQO {reference}",
            "callback_url": callback_url,
            "mode": self.mode,
        }

        try:
            response = requests.post(
                f"{self.BASE_URL}/api/orders/online/kkiapay",
                json=payload,
                headers=self.headers,
                timeout=30,
            )
            data = response.json()

            if response.status_code in (200, 201):
                return {
                    "success": True,
                    "reference": reference,
                    "feexpay_id": data.get("id") or data.get("transactionId"),
                    "status": data.get("status", "PENDING"),
                    "message": data.get("message", "Paiement initié"),
                    "raw_response": data,
                }

            logger.error("FeexPay erreur: %s — %s", response.status_code, data)
            return {
                "success": False,
                "reference": reference,
                "status": "FAILED",
                "message": data.get("message", "Erreur lors de l'initiation"),
                "raw_response": data,
            }
        except requests.Timeout:
            logger.error("FeexPay timeout pour référence %s", reference)
            return {
                "success": False,
                "reference": reference,
                "status": "TIMEOUT",
                "message": "Délai d'attente dépassé",
                "raw_response": None,
            }
        except Exception as exc:
            logger.error("FeexPay exception: %s", exc)
            return {
                "success": False,
                "reference": reference,
                "status": "ERROR",
                "message": str(exc),
                "raw_response": None,
            }

    def initiate_card_payment(
        self,
        amount: Decimal,
        phone_number: str,
        card_type: str,
        first_name: str,
        last_name: str,
        email: str,
        reference: str,
        country: str = "Benin",
        address: str = "Cotonou",
        district: str = "Littoral",
        currency: str = "XOF",
    ) -> dict:
        """Initier un paiement par carte — retourne une URL de redirection."""
        callback_url = f"{self.callback_base.rstrip('/')}/api/v1/payments/feexpay/callback/"

        payload = {
            "shop": self.shop_id,
            "amount": int(amount),
            "phone_number": phone_number,
            "type_card": card_type.upper(),
            "firstname": first_name,
            "lastname": last_name,
            "email": email,
            "country": country,
            "address": address,
            "district": district,
            "currency": currency,
            "reference": reference,
            "callback_url": callback_url,
            "mode": self.mode,
        }

        try:
            response = requests.post(
                f"{self.BASE_URL}/api/orders/online/card",
                json=payload,
                headers=self.headers,
                timeout=30,
            )
            data = response.json()

            if response.status_code in (200, 201) and data.get("url"):
                return {
                    "success": True,
                    "reference": reference,
                    "redirect_url": data["url"],
                    "status": "PENDING",
                    "message": "Redirection vers la page de paiement",
                    "raw_response": data,
                }

            logger.error("FeexPay card erreur: %s — %s", response.status_code, data)
            return {
                "success": False,
                "reference": reference,
                "redirect_url": None,
                "status": "FAILED",
                "message": data.get("message", "Erreur lors de l'initiation carte"),
                "raw_response": data,
            }
        except Exception as exc:
            logger.error("FeexPay card exception: %s", exc)
            return {
                "success": False,
                "reference": reference,
                "redirect_url": None,
                "status": "ERROR",
                "message": str(exc),
                "raw_response": None,
            }

    def get_payment_status(self, feexpay_id: str) -> dict:
        """Vérifier le statut d'une transaction FeexPay."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/api/orders/status/{feexpay_id}",
                headers=self.headers,
                timeout=15,
            )
            data = response.json()

            if response.status_code == 200:
                return {
                    "success": True,
                    "status": data.get("status"),
                    "amount": data.get("amount"),
                    "reference": data.get("reference"),
                    "raw_response": data,
                }

            return {
                "success": False,
                "status": "UNKNOWN",
                "message": data.get("message", "Impossible de vérifier"),
                "raw_response": data,
            }
        except Exception as exc:
            logger.error("FeexPay status check exception: %s", exc)
            return {"success": False, "status": "ERROR", "message": str(exc)}

    @staticmethod
    def verify_webhook_signature(payload_body: bytes, signature_header: str) -> bool:
        """
        Vérifier la signature HMAC-SHA256 du callback FeexPay.
        AUDIT FIX [P0] — Empêche le spoofing de callback.
        """
        if not signature_header:
            logger.warning("FeexPay callback sans signature header — rejeté")
            return False

        secret = getattr(settings, "FEEXPAY_WEBHOOK_SECRET", "")
        if not secret:
            logger.error("FEEXPAY_WEBHOOK_SECRET non configuré!")
            return False

        expected = hmac.new(
            secret.encode("utf-8"),
            payload_body,
            hashlib.sha256,
        ).hexdigest()

        normalized = signature_header.lower().replace("sha256=", "")
        return hmac.compare_digest(expected, normalized)

    @staticmethod
    def generate_reference(prefix: str = "FNQ") -> str:
        """Génère une référence unique pour l'idempotency."""
        return f"{prefix}-{uuid.uuid4().hex[:16].upper()}"
