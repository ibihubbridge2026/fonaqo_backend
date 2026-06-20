import json

from django.http import JsonResponse
from rest_framework.response import Response


class AccountSuspensionMiddleware:
    """Intercepts API requests from suspended accounts (is_active=False).

    JWT-authenticated users whose account has been suspended can still reach
    views if only the serializer/login path checks ``is_active``.  This
    middleware short-circuits any ``/api/`` request for an authenticated but
    inactive user before the view runs, returning a 403 with the
    ``ACCOUNT_SUSPENDED`` code understood by the Flutter app.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.path.startswith('/api/')
            and hasattr(request, 'user')
            and request.user.is_authenticated
            and not request.user.is_active
        ):
            return JsonResponse(
                {
                    'status': 'error',
                    'message': (
                        'Votre compte a été suspendu. '
                        'Contactez le support FONACO pour faire appel.'
                    ),
                    'code': 'ACCOUNT_SUSPENDED',
                    'data': {},
                },
                status=403,
            )
        return self.get_response(request)


class StandardizeJsonResponseMiddleware:
    """Wraps JSON payloads into a standard API envelope."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Handle DRF Response
        if isinstance(response, Response):
            if hasattr(response, 'data') and isinstance(response.data, dict):
                if {"status", "message", "data"}.issubset(response.data.keys()):
                    return response
            return response

        # Handle JsonResponse
        if not isinstance(response, JsonResponse):
            return response

        try:
            payload = json.loads(response.content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return response

        if isinstance(payload, dict) and {"status", "message", "data"}.issubset(payload.keys()):
            return response

        success = 200 <= response.status_code < 400
        wrapped = {
            "status": "success" if success else "error",
            "message": "Request successful" if success else "Request failed",
            "data": payload if success else {},
            "errors": payload if not success else {},
        }
        return JsonResponse(wrapped, status=response.status_code)
