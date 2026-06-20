"""API badge professionnel agent — paiement unique 1 000 FCFA."""

from decimal import Decimal

from django.db import transaction as db_transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import AgentProfile
from apps.accounts.pro_badge import build_agent_pro_badge_pdf
from apps.core.choices import AgentBadgeStatus, TransactionStatus
from apps.wallets.models import Transaction, Wallet

BADGE_FEE_FCFA = Decimal('1000')


def _badge_payload(profile):
    return {
        'badge_status': profile.badge_status,
        'badge_paid': profile.badge_paid,
        'agent_code': profile.agent_code,
        'is_internal': profile.is_internal,
        'badge_photo_url': profile.badge_photo.url if profile.badge_photo else None,
        'badge_requested_at': (
            profile.badge_requested_at.isoformat() if profile.badge_requested_at else None
        ),
        'badge_approved_at': (
            profile.badge_approved_at.isoformat() if profile.badge_approved_at else None
        ),
        'can_request': profile.badge_status in (
            AgentBadgeStatus.NONE,
            AgentBadgeStatus.REJECTED,
        ),
        'can_download': profile.badge_status == AgentBadgeStatus.APPROVED,
        'fee_fcfa': int(BADGE_FEE_FCFA),
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_badge_status_view(request):
    if not request.user.is_agent:
        return Response({'error': 'Réservé aux agents'}, status=status.HTTP_403_FORBIDDEN)
    profile, _ = AgentProfile.objects.get_or_create(user=request.user)
    return Response({'status': 'success', 'data': _badge_payload(profile)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def agent_badge_request_view(request):
    """Demande de badge professionnel — 1 000 FCFA facturés une seule fois à vie."""
    if not request.user.is_agent:
        return Response({'error': 'Réservé aux agents'}, status=status.HTTP_403_FORBIDDEN)

    photo = request.FILES.get('badge_photo') or request.FILES.get('photo')
    if not photo:
        return Response(
            {'error': 'Photo dédiée au badge requise'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with db_transaction.atomic():
        profile, _ = AgentProfile.objects.select_for_update().get_or_create(user=request.user)

        if profile.badge_status == AgentBadgeStatus.PENDING:
            return Response(
                {'error': 'Une demande est déjà en cours de traitement'},
                status=status.HTTP_409_CONFLICT,
            )
        if profile.badge_status == AgentBadgeStatus.APPROVED:
            return Response(
                {'error': 'Badge déjà validé — utilisez le téléchargement'},
                status=status.HTTP_409_CONFLICT,
            )

        # Prélever 1 000 FCFA si ce n'est pas déjà payé
        if not profile.badge_paid:
            wallet, _ = Wallet.objects.get_or_create(user=request.user)
            wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
            if wallet.balance < BADGE_FEE_FCFA:
                return Response(
                    {
                        'error': (
                            f'Solde insuffisant. Le badge professionnel coûte '
                            f'{int(BADGE_FEE_FCFA)} FCFA (paiement unique à vie). '
                            f'Votre solde : {wallet.balance} FCFA.'
                        )
                    },
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )
            wallet.balance -= BADGE_FEE_FCFA
            wallet.save(update_fields=['balance', 'updated_at'])

            Transaction.objects.create(
                wallet=wallet,
                amount=-BADGE_FEE_FCFA,
                transaction_type=Transaction.TransactionType.BADGE_FEE,
                status=TransactionStatus.COMPLETED,
                description='Badge professionnel FONACO — paiement unique (valable à vie)',
            )
            profile.badge_paid = True

        profile.badge_photo = photo
        profile.badge_status = AgentBadgeStatus.PENDING
        profile.badge_requested_at = timezone.now()
        profile.badge_rejection_reason = ''
        profile.save(update_fields=[
            'badge_paid', 'badge_photo', 'badge_status',
            'badge_requested_at', 'badge_rejection_reason', 'updated_at',
        ])

    return Response({
        'status': 'success',
        'message': 'Demande de badge envoyée. Vous serez notifié par email après validation.',
        'data': _badge_payload(profile),
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_badge_download_view(request):
    if not request.user.is_agent:
        return Response({'error': 'Réservé aux agents'}, status=status.HTTP_403_FORBIDDEN)

    profile, _ = AgentProfile.objects.get_or_create(user=request.user)
    if profile.badge_status != AgentBadgeStatus.APPROVED:
        return Response(
            {'error': 'Badge non encore validé par le staff'},
            status=status.HTTP_403_FORBIDDEN,
        )

    pdf_bytes = build_agent_pro_badge_pdf(request.user, profile)
    filename = f'badge-{profile.agent_code or request.user.username}.pdf'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
