from django.db import connection
from django.urls import get_resolver, reverse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


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
