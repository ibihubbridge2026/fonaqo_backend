from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response

from apps.core.admin_audit import log_admin_action
from apps.core.choices import AgentKYCStatus

User = get_user_model()


def _agent_profile_model():
    from apps.accounts.models import AgentProfile

    return AgentProfile


def _kyc_status_enum():
    return AgentKYCStatus


def _serialize_profile(profile):
    user = profile.user
    return {
        'id': profile.pk,
        'user_id': user.pk,
        'username': user.username,
        'email': user.email,
        'full_name': user.get_full_name() or user.username,
        'kyc_status': profile.kyc_status,
        'id_card_photo': profile.id_card_photo.url if profile.id_card_photo else None,
        'selfie_photo': profile.selfie_photo.url if profile.selfie_photo else None,
        'agent_code': profile.agent_code,
        'is_internal': profile.is_internal,
        'badge_status': profile.badge_status,
        'updated_at': profile.updated_at.isoformat() if profile.updated_at else None,
    }


_STAFF_AUTH = [SessionAuthentication, JWTAuthentication]


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def kyc_queue(request):
    """File KYC en attente (staff / super admin — UI à venir)."""
    AgentProfile = _agent_profile_model()
    AgentKYCStatus = _kyc_status_enum()

    status_filter = request.query_params.get('status')
    qs = AgentProfile.objects.select_related('user').order_by('updated_at')
    if status_filter:
        qs = qs.filter(kyc_status=status_filter)
    else:
        qs = qs.filter(kyc_status__in=[
            AgentKYCStatus.SUBMITTED,
            AgentKYCStatus.PENDING,
        ])

    return Response({
        'count': qs.count(),
        'results': [_serialize_profile(p) for p in qs[:100]],
    })


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def kyc_approve(request, profile_id):
    """Approuver le KYC d'un agent."""
    AgentProfile = _agent_profile_model()
    AgentKYCStatus = _kyc_status_enum()

    try:
        profile = AgentProfile.objects.select_related('user').get(pk=profile_id)
    except AgentProfile.DoesNotExist:
        return Response({'error': 'Profil agent introuvable'}, status=status.HTTP_404_NOT_FOUND)

    profile.kyc_status = AgentKYCStatus.APPROVED
    profile.save(update_fields=['kyc_status', 'updated_at'])
    user = profile.user
    if not user.is_verified:
        user.is_verified = True
        user.save(update_fields=['is_verified'])
    from apps.accounts.agent_codes import ensure_agent_code
    ensure_agent_code(profile)
    from apps.core.email_service import send_kyc_approved_email
    send_kyc_approved_email(user)
    log_admin_action(
        request.user, 'KYC_APPROVE',
        target_type='AgentProfile', target_id=profile_id,
        detail=f'@{user.username}',
    )
    return Response(_serialize_profile(profile))


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def kyc_reject(request, profile_id):
    """Rejeter le KYC d'un agent."""
    AgentProfile = _agent_profile_model()
    AgentKYCStatus = _kyc_status_enum()

    reason = request.data.get('reason', '')
    try:
        profile = AgentProfile.objects.select_related('user').get(pk=profile_id)
    except AgentProfile.DoesNotExist:
        return Response({'error': 'Profil agent introuvable'}, status=status.HTTP_404_NOT_FOUND)

    profile.kyc_status = AgentKYCStatus.REJECTED
    profile.rejection_reason = reason
    profile.save(update_fields=['kyc_status', 'rejection_reason', 'updated_at'])
    log_admin_action(
        request.user, 'KYC_REJECT',
        target_type='AgentProfile', target_id=profile_id,
        detail=reason or f'@{profile.user.username}',
    )
    from apps.core.email_service import send_kyc_rejected_email
    send_kyc_rejected_email(profile.user, reason)
    data = _serialize_profile(profile)
    data['rejection_reason'] = reason
    return Response(data)
