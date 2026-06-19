"""API badge professionnel agent."""

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import AgentProfile
from apps.accounts.pro_badge import build_agent_pro_badge_pdf
from apps.core.choices import AgentBadgeStatus


def _badge_payload(profile):
    return {
        'badge_status': profile.badge_status,
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
    if not request.user.is_agent:
        return Response({'error': 'Réservé aux agents'}, status=status.HTTP_403_FORBIDDEN)

    photo = request.FILES.get('badge_photo') or request.FILES.get('photo')
    if not photo:
        return Response(
            {'error': 'Photo dédiée au badge requise'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    profile, _ = AgentProfile.objects.get_or_create(user=request.user)
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

    profile.badge_photo = photo
    profile.badge_status = AgentBadgeStatus.PENDING
    profile.badge_requested_at = timezone.now()
    profile.badge_rejection_reason = ''
    profile.save(update_fields=[
        'badge_photo', 'badge_status', 'badge_requested_at',
        'badge_rejection_reason', 'updated_at',
    ])
    return Response({
        'status': 'success',
        'message': 'Demande de badge envoyée',
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
