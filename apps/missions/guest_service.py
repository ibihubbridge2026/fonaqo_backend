from __future__ import annotations

import logging
import random
import secrets
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.core.services import PlatformConfigService
from apps.escrow.services import EscrowService, PLATFORM_COMMISSION_RATE
from apps.payments.models import Payment
from apps.payments.services import FeexPayService

logger = logging.getLogger(__name__)
User = get_user_model()

GUEST_LABOR_BASE_FCFA = Decimal('3500')
GUEST_LABOR_CHAR_RATE = Decimal('100')
GUEST_LABOR_MIN_FCFA = Decimal('3500')
GUEST_LABOR_MAX_FCFA = Decimal('150000')
GUEST_LABOR_ROUND_FCFA = Decimal('500')


class GuestTrackingCodeGenerator:
    """Génère un code de suivi opaque unique (ex: FNC-4829-BJ)."""

    @staticmethod
    def generate(country_suffix: str = 'BJ') -> str:
        suffix = (country_suffix or 'BJ').upper()[:2]
        for _ in range(50):
            digits = random.randint(1000, 9999)
            code = f'FNC-{digits}-{suffix}'
            from apps.missions.models import Mission
            if not Mission.objects.filter(tracking_code=code).exists():
                return code
        fallback = f'FNC-{secrets.token_hex(3).upper()}-{suffix}'
        return fallback[:20]


class GuestLaborEstimator:
    """Estimation simple de la main-d'œuvre à partir de la description."""

    @classmethod
    def estimate(cls, description: str) -> Decimal:
        text = (description or '').strip()
        length = len(text)
        extra_blocks = max(0, length // 20)
        raw = GUEST_LABOR_BASE_FCFA + (GUEST_LABOR_CHAR_RATE * extra_blocks)
        clamped = max(GUEST_LABOR_MIN_FCFA, min(GUEST_LABOR_MAX_FCFA, raw))
        rounded = (
            (clamped / GUEST_LABOR_ROUND_FCFA).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            * GUEST_LABOR_ROUND_FCFA
        )
        return rounded


class GuestUserProvisioner:
    """Crée ou récupère un compte client pour le parcours invité."""

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        raw = (phone or '').strip().replace(' ', '')
        if raw and not raw.startswith('+'):
            if raw.startswith('00'):
                raw = '+' + raw[2:]
            elif raw.startswith('0'):
                raw = '+229' + raw[1:]
            else:
                raw = '+' + raw
        return raw

    @classmethod
    @transaction.atomic
    def get_or_create(cls, *, email: str, phone: str) -> tuple[User, bool]:
        from apps.accounts.models import ClientProfile

        email_norm = (email or '').strip().lower()
        phone_norm = cls._normalize_phone(phone)
        if not email_norm:
            raise ValueError('Email requis.')
        if not phone_norm:
            raise ValueError('Téléphone requis.')

        user = User.objects.filter(email__iexact=email_norm).first()
        if not user:
            user = User.objects.filter(phone_number=phone_norm).first()

        created = False
        if user:
            if not user.is_client:
                user.is_client = True
                user.save(update_fields=['is_client'])
        else:
            username_base = email_norm.split('@')[0][:20]
            username = username_base
            idx = 1
            while User.objects.filter(username=username).exists():
                username = f'{username_base}{idx}'[:30]
                idx += 1
            password = secrets.token_urlsafe(16)
            user = User.objects.create_user(
                username=username,
                email=email_norm,
                phone_number=phone_norm,
                password=password,
                is_client=True,
                is_guest=True,
            )
            created = True

        ClientProfile.objects.get_or_create(user=user)
        return user, created


class GuestMissionEmailService:
    """E-mail transactionnel post-création mission invité."""

    @staticmethod
    def send(*, user: User, mission, tracking_code: str, track_url: str) -> None:
        subject = f'FONACO — Mission enregistrée [{tracking_code}]'
        message = f'''Bonjour,

Votre demande de mission sur FONACO a bien été enregistrée.

Code de suivi : {tracking_code}
Suivre ma mission : {track_url}

Les fonds seront sécurisés en séquestre (Escrow) jusqu'à la validation de la prestation.

Récupérer votre compte sur l'application mobile :
1. Téléchargez l'app FONACO
2. Utilisez « Mot de passe oublié » avec l'adresse {user.email}
3. Vous retrouverez l'historique de cette mission

Cordialement,
L'équipe FONACO
'''
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@fonaco.com'),
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception as exc:
            logger.warning('Email guest mission non envoyé: %s', exc)


class GuestMissionCreator:
    """Orchestre création mission invité + intention de paiement Escrow."""

    @classmethod
    @transaction.atomic
    def create(
        cls,
        *,
        email: str,
        phone: str,
        description: str,
        address: str,
        latitude: float | None = None,
        longitude: float | None = None,
        payment_method: str = 'MTN',
    ) -> dict:
        from apps.missions.models import Mission, MissionTimelineEvent

        user, _ = GuestUserProvisioner.get_or_create(email=email, phone=phone)

        lat = latitude if latitude is not None else 6.3703
        lng = longitude if longitude is not None else 2.3912
        labor = GuestLaborEstimator.estimate(description)
        options_fee = PlatformConfigService.mission_options_fee(
            is_urgent=False,
            is_confidential=False,
        )
        platform_fee = (labor * PLATFORM_COMMISSION_RATE + options_fee).quantize(
            Decimal('0.01'),
        )
        total = labor + platform_fee
        tracking_code = GuestTrackingCodeGenerator.generate()
        title = (description or 'Mission web').strip()[:255]
        if len(title) < 5:
            title = f'Mission {tracking_code}'

        mission = Mission.objects.create(
            client=user,
            title=title,
            description=description.strip(),
            address=address.strip(),
            location=Point(lng, lat, srid=4326),
            price=total,
            labor_cost=labor,
            service_amount=labor,
            service_fee=platform_fee,
            material_cost=Decimal('0'),
            purchase_amount=Decimal('0'),
            status='PENDING',
            tracking_code=tracking_code,
        )

        MissionTimelineEvent.objects.create(
            mission=mission,
            event_type='created',
            performed_by=user,
            notes='Création via parcours invité web',
        )

        payment = FeexPayService.init_payment(
            user=user,
            amount=total,
            purpose=Payment.Purpose.MISSION_PAYMENT,
            metadata={
                'mission_id': str(mission.id),
                'tracking_code': tracking_code,
                'source': 'guest_web',
            },
            payment_method=payment_method,
        )

        site_base = getattr(settings, 'SITE_BASE_URL', 'http://localhost:8000').rstrip('/')
        track_url = f'{site_base}/vitrine/suivi/?ref={tracking_code}'

        GuestMissionEmailService.send(
            user=user,
            mission=mission,
            tracking_code=tracking_code,
            track_url=track_url,
        )

        try:
            from apps.missions.tasks import check_pending_mission_alert
            from apps.missions.views import _notify_agents_new_mission

            _notify_agents_new_mission(mission)
            check_pending_mission_alert.apply_async(
                args=[str(mission.id)],
                countdown=300,
            )
        except Exception as exc:
            logger.debug('Notifications guest mission: %s', exc)

        checkout_url = None
        if not getattr(settings, 'FEEXPAY_SANDBOX', True):
            checkout_url = getattr(settings, 'FEEXPAY_CHECKOUT_URL_TEMPLATE', '').format(
                ref=payment.external_reference,
            ) or None

        return {
            'mission_id': str(mission.id),
            'tracking_code': tracking_code,
            'track_url': track_url,
            'payment_id': str(payment.id),
            'payment_amount': int(payment.amount),
            'external_reference': payment.external_reference,
            'labor_estimate': float(labor),
            'service_fee': float(platform_fee),
            'total_amount': float(total),
            'checkout_url': checkout_url,
            'sandbox': getattr(settings, 'FEEXPAY_SANDBOX', True),
        }
