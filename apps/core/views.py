from django.db import connection
from django.urls import get_resolver, reverse
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import AdminNotification
from .services import (
    FEES_CONFIDENTIAL_KEY,
    FEES_URGENT_KEY,
    PlatformConfigService,
)

_STAFF_AUTH = [SessionAuthentication, JWTAuthentication]


def _route_registered(prefix: str, name: str) -> bool:
    try:
        reverse(name)
        return True
    except Exception:
        resolver = get_resolver()
        for pattern in resolver.url_patterns:
            pattern_str = getattr(pattern, 'pattern', None)
            if pattern_str and prefix in str(pattern_str):
                return True
        return False


def _websocket_patterns_available() -> bool:
    try:
        from apps.core.routing import websocket_urlpatterns

        return len(websocket_urlpatterns) >= 2
    except Exception:
        return False


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Healthcheck pour déploiement et diagnostic routes custom missions."""
    db_ok = False
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        db_ok = True
    except Exception:
        db_ok = False

    mission_routes = {
        'active': _route_registered('missions/active', 'mission-active'),
        'assigned': _route_registered('missions/assigned', 'mission-assigned'),
        'rate': _route_registered('missions', 'mission-rate-agent'),
    }

    websocket_routes = {
        'gps': _websocket_patterns_available(),
        'timeline': _websocket_patterns_available(),
    }

    staff_routes = {
        'kyc_queue': _route_registered('staff/kyc', 'staff-kyc-queue'),
    }

    status_label = 'ok' if db_ok else 'degraded'
    return Response({
        'status': status_label,
        'service': 'fonaqo-api',
        'checks': {
            'database': db_ok,
            'mission_routes': mission_routes,
            'websocket_routes': websocket_routes,
            'staff_routes': staff_routes,
        },
        'api_versions': ['v1', 'v2'],
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def platform_fees(request):
    """Frais dynamiques mission urgente / agent interne (FCFA)."""
    return Response({
        'fees_urgent': int(
            PlatformConfigService.get_decimal(FEES_URGENT_KEY, '500'),
        ),
        'fees_confidential': int(
            PlatformConfigService.get_decimal(FEES_CONFIDENTIAL_KEY, '500'),
        ),
    })


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def admin_notifications(request):
    """Alertes opérationnelles pour le panel SuperAdmin."""
    unread_only = request.query_params.get('unread', 'true').lower() in (
        'true', '1', 'yes',
    )
    qs = AdminNotification.objects.select_related('mission').order_by('-created_at')
    if unread_only:
        qs = qs.filter(is_read=False)
    limit = min(int(request.query_params.get('limit', 50)), 200)
    rows = []
    for item in qs[:limit]:
        rows.append({
            'id': item.id,
            'category': item.category,
            'severity': item.severity,
            'title': item.title,
            'message': item.message,
            'mission_id': str(item.mission_id) if item.mission_id else None,
            'is_read': item.is_read,
            'metadata': item.metadata,
            'created_at': item.created_at.isoformat(),
        })
    return Response({'results': rows, 'count': len(rows)})


@api_view(['PATCH', 'POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def admin_notification_mark_read(request, notification_id):
    """Marque une alerte admin comme lue."""
    try:
        notif = AdminNotification.objects.get(pk=notification_id)
    except AdminNotification.DoesNotExist:
        return Response({'message': 'Notification introuvable'}, status=404)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    return Response({'status': 'ok', 'id': notif.id})
