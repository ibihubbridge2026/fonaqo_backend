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
from apps.finance import ledger_integration

from .models import Payment
from .feexpay_service import FeexPayClient

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
      wallet_txn = Transaction.objects.create(
        wallet=wallet,
        amount=amount,
        transaction_type=Transaction.TransactionType.DEPOSIT,
        status=TransactionStatus.COMPLETED,
        reference=payment.external_reference,
        description=(
          f'Recharge FeexPay {payment.external_reference or payment.id}'
        ),
      )
      ledger_integration.record_feexpay_deposit(
        user_id=payment.user_id,
        amount=amount,
        payment_id=payment.id,
        external_reference=payment.external_reference,
        wallet_transaction_id=wallet_txn.id,
      )
    elif payment.purpose == Payment.Purpose.MISSION_PAYMENT:
      wallet, _ = Wallet.objects.get_or_create(user=payment.user)
      wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
      wallet.balance += amount
      wallet.save(update_fields=['balance', 'updated_at'])
      mission_id = (payment.metadata or {}).get('mission_id', '')
      wallet_txn = Transaction.objects.create(
        wallet=wallet,
        amount=amount,
        transaction_type=Transaction.TransactionType.DEPOSIT,
        status=TransactionStatus.COMPLETED,
        description=(
          f'Séquestre mission (pré-financement) {mission_id} '
          f'— {payment.external_reference or payment.id}'
        ),
      )
      ledger_integration.record_feexpay_deposit(
        user_id=payment.user_id,
        amount=amount,
        payment_id=payment.id,
        external_reference=payment.external_reference,
        wallet_transaction_id=wallet_txn.id,
      )
    elif payment.purpose == Payment.Purpose.BOOST_PURCHASE:
      from apps.escrow.services import get_platform_wallet
      platform_wallet = Wallet.objects.select_for_update().get(
        pk=get_platform_wallet().pk,
      )
      platform_wallet.balance += amount
      platform_wallet.save(update_fields=['balance', 'updated_at'])
      platform_txn = Transaction.objects.create(
        wallet=platform_wallet,
        amount=amount,
        transaction_type=Transaction.TransactionType.DEPOSIT,
        status=TransactionStatus.COMPLETED,
        reference=payment.external_reference,
        description=(
          f'Revenu boost FeexPay {payment.external_reference or payment.id}'
        ),
      )
      ledger_integration.record_boost_feexpay(
        user_id=payment.user_id,
        amount=amount,
        payment_id=payment.id,
        wallet_transaction_id=platform_txn.id,
        external_reference=payment.external_reference,
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
  @transaction.atomic
  def handle_webhook(payload: dict) -> Payment | None:
    """Traite un callback FeexPay et crédite le wallet si succès (idempotent)."""
    external_id = payload.get('external_id') or payload.get('payment_id')
    reference = (
      payload.get('reference')
      or payload.get('external_reference')
      or payload.get('transaction_id')
    )
    provider_tx_id = payload.get('transaction_id') or payload.get('id')
    status_raw = (payload.get('status') or '').upper()

    if status_raw not in ('SUCCESS', 'SUCCESSFUL', 'COMPLETED', 'PAID'):
      return None

    # Idempotency : vérifier si ce provider_transaction_id a déjà été traité
    if provider_tx_id:
      existing_payment = Payment.objects.filter(
        provider_transaction_id=provider_tx_id,
        status=PaymentStatus.SUCCESS
      ).first()
      if existing_payment:
        logger.info('Webhook FeexPay: transaction déjà traitée %s', provider_tx_id)
        return existing_payment

    payment = None
    if external_id:
      payment = Payment.objects.select_for_update().filter(pk=external_id).first()
    if payment is None and reference:
      payment = Payment.objects.select_for_update().filter(external_reference=reference).first()
    if payment is None:
      logger.warning('Webhook FeexPay: paiement introuvable %s', payload)
      return None

    # Enregistrer provider_transaction_id pour idempotency future
    if provider_tx_id and not payment.provider_transaction_id:
      payment.provider_transaction_id = provider_tx_id
      payment.save(update_fields=['provider_transaction_id'])

    return FeexPayService.apply_success(payment, feex_reference=reference)

  @staticmethod
  def generate_reference(prefix: str = 'DEP') -> str:
    return FeexPayClient.generate_reference(prefix)

  @staticmethod
  def initiate_wallet_deposit(
    user,
    amount,
    phone_number: str,
    network: str = 'MTN',
    payment_method: str = 'MOBILE',
    card_type: str = 'VISA',
  ) -> tuple[Payment, dict]:
    """
    Initie une recharge wallet via FeexPay (Mobile Money ou Carte).
    AUDIT FIX [P0+P1] — Crée Payment avant appel API pour idempotency.
    """
    amount_int = _quantize_fcfa(amount)
    if amount_int < 100:
      raise ValueError('Montant minimal : 100 XOF')
    if amount_int > 5_000_000:
      raise ValueError('Montant maximal : 5 000 000 XOF')

    reference = FeexPayClient.generate_reference('DEP')
    payment = Payment.objects.create(
      user=user,
      amount=amount_int,
      status=PaymentStatus.PENDING,
      purpose=Payment.Purpose.WALLET_DEPOSIT,
      payment_method=payment_method.upper(),
      external_reference=reference,
      metadata={
        'phone_number': phone_number,
        'network': network,
        'card_type': card_type,
      },
    )

    if getattr(settings, 'FEEXPAY_SANDBOX', True):
      return payment, {
        'success': True,
        'reference': reference,
        'status': 'PENDING',
        'message': 'Paiement sandbox initié — confirmez via /feexpay/confirm/',
        'feexpay_id': None,
      }

    client = FeexPayClient()
    full_name = user.get_full_name() or user.username
    email = user.email or f'{user.username}@fonaqo.com'

    if payment_method.upper() == 'MOBILE':
      result = client.initiate_mobile_payment(
        amount=amount_int,
        phone_number=phone_number,
        network=network,
        full_name=full_name,
        email=email,
        reference=reference,
        description=f'Recharge wallet {user.username}',
      )
    elif payment_method.upper() == 'CARD':
      result = client.initiate_card_payment(
        amount=amount_int,
        phone_number=phone_number,
        card_type=card_type,
        first_name=user.first_name or user.username,
        last_name=user.last_name or '',
        email=email,
        reference=reference,
      )
    else:
      raise ValueError('Méthode de paiement invalide (MOBILE ou CARD)')

    if result.get('feexpay_id'):
      payment.provider_transaction_id = str(result['feexpay_id'])
      payment.metadata = {**payment.metadata, 'raw_response': result.get('raw_response')}
      payment.save(update_fields=['provider_transaction_id', 'metadata', 'updated_at'])

    if not result.get('success'):
      payment.status = PaymentStatus.FAILED
      payment.metadata = {
        **payment.metadata,
        'error_message': result.get('message', ''),
      }
      payment.save(update_fields=['status', 'metadata', 'updated_at'])

    return payment, result

  @staticmethod
  def refresh_payment_status(payment: Payment) -> Payment:
    """Interroge FeexPay si le paiement est encore PENDING."""
    if payment.status != PaymentStatus.PENDING or not payment.provider_transaction_id:
      return payment

    client = FeexPayClient()
    live = client.get_payment_status(payment.provider_transaction_id)
    if not live.get('success'):
      return payment

    new_status = (live.get('status') or '').upper()
    if new_status in ('SUCCESS', 'SUCCESSFUL', 'COMPLETED', 'PAID'):
      return FeexPayService.apply_success(payment, feex_reference=payment.external_reference)
    if new_status in ('FAILED', 'CANCELLED', 'REJECTED'):
      payment.status = PaymentStatus.FAILED
      payment.save(update_fields=['status', 'updated_at'])
    return payment
