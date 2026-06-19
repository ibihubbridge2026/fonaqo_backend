from __future__ import annotations

import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.choices import PaymentStatus, TransactionStatus
from apps.wallets.models import Transaction, Wallet

from .models import Payment

logger = logging.getLogger(__name__)


def _quantize_fcfa(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


class FeexPayService:
  BASE_URL = getattr(settings, 'FEEXPAY_BASE_URL', 'https://api.feexpay.me/backend')

  @staticmethod
  def init_payment(user, amount, purpose, metadata=None, payment_method='MTN'):
    """Crée un paiement FeexPay en attente et retourne l'enregistrement local."""
    amount_int = _quantize_fcfa(amount)
    if amount_int <= 0:
      raise ValueError('Le montant doit être positif')

    external_ref = f'FEEX-{uuid.uuid4().hex[:16].upper()}'
    payment = Payment.objects.create(
      user=user,
      amount=amount_int,
      status=PaymentStatus.PENDING,
      purpose=purpose,
      payment_method=payment_method,
      external_reference=external_ref,
      metadata=metadata or {},
    )

    if getattr(settings, 'FEEXPAY_SANDBOX', True):
      return payment

    payload = {
      'amount': int(amount_int),
      'currency': 'XOF',
      'description': f'FONAQO {purpose} — {user.email or user.username}',
      'callback_url': getattr(settings, 'FEEXPAY_CALLBACK_URL', ''),
      'external_id': str(payment.id),
      'reference': external_ref,
      'token': getattr(settings, 'FEEXPAY_API_KEY', ''),
    }
    try:
      response = requests.post(
        f'{FeexPayService.BASE_URL}/v1/transaction/init',
        json=payload,
        timeout=30,
      )
      response.raise_for_status()
      data = response.json()
      feex_ref = data.get('reference') or data.get('transaction_id')
      if feex_ref:
        payment.external_reference = str(feex_ref)
        payment.save(update_fields=['external_reference', 'updated_at'])
    except Exception as exc:
      logger.warning('FeexPay init API indisponible: %s', exc)

    return payment

  @staticmethod
  @transaction.atomic
  def apply_success(payment: Payment, feex_reference: str | None = None) -> Payment:
    """Marque un paiement réussi et applique l'effet métier (wallet, etc.)."""
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status == PaymentStatus.SUCCESS:
      return payment

    if feex_reference and not payment.external_reference:
      payment.external_reference = feex_reference

    payment.status = PaymentStatus.SUCCESS
    payment.save(update_fields=['status', 'external_reference', 'updated_at'])

    amount = _quantize_fcfa(payment.amount)

    if payment.purpose == Payment.Purpose.WALLET_DEPOSIT:
      wallet, _ = Wallet.objects.get_or_create(user=payment.user)
      wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
      wallet.balance += amount
      wallet.save(update_fields=['balance', 'updated_at'])
      Transaction.objects.create(
        wallet=wallet,
        amount=amount,
        transaction_type=Transaction.TransactionType.DEPOSIT,
        status=TransactionStatus.COMPLETED,
        description=(
          f'Recharge FeexPay {payment.external_reference or payment.id}'
        ),
      )
    elif payment.purpose == Payment.Purpose.MISSION_PAYMENT:
      wallet, _ = Wallet.objects.get_or_create(user=payment.user)
      wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
      wallet.balance += amount
      wallet.save(update_fields=['balance', 'updated_at'])
      mission_id = (payment.metadata or {}).get('mission_id', '')
      Transaction.objects.create(
        wallet=wallet,
        amount=amount,
        transaction_type=Transaction.TransactionType.DEPOSIT,
        status=TransactionStatus.COMPLETED,
        description=(
          f'Séquestre mission (pré-financement) {mission_id} '
          f'— {payment.external_reference or payment.id}'
        ),
      )
    return payment

  @staticmethod
  @transaction.atomic
  def verify_payment(user, transaction_id: str, expected_amount=None, purpose=None, metadata=None) -> Payment:
    """Vérifie qu'un paiement FeexPay est réussi (sandbox : auto-succès immédiat)."""
    if not transaction_id:
      raise ValueError('Référence FeexPay requise')

    payment = Payment.objects.select_for_update().filter(
      user=user,
      external_reference=transaction_id,
    ).first()

    if payment and payment.status == PaymentStatus.SUCCESS:
      if expected_amount is not None:
        expected = _quantize_fcfa(expected_amount)
        if payment.amount != expected:
          raise ValueError('Montant du paiement FeexPay incorrect')
      return payment

    if getattr(settings, 'FEEXPAY_SANDBOX', True):
      amount = _quantize_fcfa(expected_amount or 0)
      if amount <= 0:
        raise ValueError('Montant requis pour la simulation FeexPay')
      if not payment:
        payment = Payment.objects.create(
          user=user,
          amount=amount,
          status=PaymentStatus.PENDING,
          purpose=purpose or Payment.Purpose.WALLET_DEPOSIT,
          payment_method='FEEXPAY_STUB',
          external_reference=transaction_id,
          metadata=metadata or {},
        )
      return FeexPayService.apply_success(payment, feex_reference=transaction_id)

    raise ValueError('Paiement FeexPay introuvable ou non confirmé')

  @staticmethod
  def handle_webhook(payload: dict) -> Payment | None:
    """Traite un callback FeexPay et crédite le wallet si succès."""
    external_id = payload.get('external_id') or payload.get('payment_id')
    reference = payload.get('reference') or payload.get('transaction_id')
    status_raw = (payload.get('status') or '').upper()

    if status_raw not in ('SUCCESS', 'SUCCESSFUL', 'COMPLETED', 'PAID'):
      return None

    payment = None
    if external_id:
      payment = Payment.objects.filter(pk=external_id).first()
    if payment is None and reference:
      payment = Payment.objects.filter(external_reference=reference).first()
    if payment is None:
      logger.warning('Webhook FeexPay: paiement introuvable %s', payload)
      return None

    return FeexPayService.apply_success(payment, feex_reference=reference)
