"""Configuration publique consommée par l'app mobile."""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.models import SupportFaqEntry
from apps.core.services import PlatformConfigService

SUPPORT_PHONE_KEY = 'SUPPORT_PHONE'
SUPPORT_EMAIL_KEY = 'SUPPORT_EMAIL'
SUPPORT_HOURS_KEY = 'SUPPORT_HOURS'


def _audience_for_user(user):
    if not user or not user.is_authenticated:
        return 'client'
    if user.is_agent:
        return 'agent'
    return 'client'


@api_view(['GET'])
@permission_classes([AllowAny])
def support_config(request):
    """
    GET /api/v1/config/support/
    FAQ + contacts support selon le rôle connecté (client/agent).
    """
    audience = _audience_for_user(request.user)
    faqs = SupportFaqEntry.objects.filter(is_active=True).filter(
        audience__in=[SupportFaqEntry.Audience.ALL, audience],
    )
    return Response({
        'phone': PlatformConfigService.get_raw(SUPPORT_PHONE_KEY, '+229 00 00 00 00'),
        'email': PlatformConfigService.get_raw(SUPPORT_EMAIL_KEY, 'support@fonaco.com'),
        'hours': PlatformConfigService.get_raw(SUPPORT_HOURS_KEY, 'Lun–Ven 8h–18h'),
        'audience': audience,
        'faqs': [
            {
                'id': f.id,
                'question': f.question,
                'answer': f.answer,
            }
            for f in faqs
        ],
    })
