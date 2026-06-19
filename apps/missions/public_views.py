from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.payments.models import Payment
from apps.payments.services import FeexPayService

from .guest_service import GuestMissionCreator
from .tracking_payload import build_mission_track_payload, resolve_mission_by_reference


@api_view(['POST'])
@permission_classes([AllowAny])
def guest_mission_create(request):
    """
    Création mission parcours invité (sans auth).
    Corps JSON : email, phone, description, address, latitude?, longitude?, payment_method?
    """
    data = request.data
    email = (data.get('email') or '').strip()
    phone = (data.get('phone') or '').strip()
    description = (data.get('description') or '').strip()
    address = (data.get('address') or '').strip()
    payment_method = (data.get('payment_method') or 'MTN').strip()

    if not all([email, phone, description, address]):
        return Response(
            {'message': 'email, phone, description et address sont obligatoires.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        lat = float(data['latitude']) if data.get('latitude') not in (None, '') else None
        lng = float(data['longitude']) if data.get('longitude') not in (None, '') else None
    except (TypeError, ValueError):
        return Response(
            {'message': 'latitude/longitude invalides.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        result = GuestMissionCreator.create(
            email=email,
            phone=phone,
            description=description,
            address=address,
            latitude=lat,
            longitude=lng,
            payment_method=payment_method,
        )
    except ValueError as exc:
        return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return Response(
            {'message': f'Impossible de créer la mission: {exc}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(result, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_mission_track(request):
    """Suivi public par tracking_code (FNC-XXXX-BJ) ou UUID / préfixe."""
    ref = request.query_params.get('reference', '')
    if len((ref or '').strip().replace('#', '')) < 4:
        return Response(
            {'found': False, 'message': 'Référence trop courte.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    mission = resolve_mission_by_reference(ref)
    if not mission:
        return Response(
            {'found': False, 'message': 'Aucune mission trouvée pour cette référence.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    mission = (
        type(mission).objects.select_related('client', 'agent')
        .prefetch_related('proofs', 'timeline_events', 'agent__offered_services')
        .filter(pk=mission.pk)
        .first()
    )
    return Response({
        'found': True,
        'mission': build_mission_track_payload(mission, request=request),
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def guest_payment_confirm(request):
    """
    Confirmation paiement invité (sandbox ou retour agrégateur).
    Corps : payment_id, tracking_code, external_reference? (optionnel)
    """
    payment_id = request.data.get('payment_id')
    tracking_code = (request.data.get('tracking_code') or '').strip().upper()
    external_reference = request.data.get('external_reference')

    if not payment_id or not tracking_code:
        return Response(
            {'message': 'payment_id et tracking_code requis.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    mission = resolve_mission_by_reference(tracking_code)
    if not mission:
        return Response({'message': 'Mission introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    payment = Payment.objects.filter(
        pk=payment_id,
        purpose=Payment.Purpose.MISSION_PAYMENT,
        metadata__mission_id=str(mission.id),
    ).first()
    if not payment:
        return Response({'message': 'Paiement introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    if getattr(settings, 'FEEXPAY_SANDBOX', True) is False and not external_reference:
        return Response(
            {'message': 'external_reference requis hors sandbox.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payment = FeexPayService.apply_success(
        payment,
        feex_reference=external_reference or payment.external_reference,
    )

    return Response({
        'status': 'ok',
        'payment_id': str(payment.id),
        'payment_status': payment.status,
        'tracking_code': mission.tracking_code,
        'track_url': f'/vitrine/suivi/?ref={mission.tracking_code}',
    })
