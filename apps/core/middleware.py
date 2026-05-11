import json

from django.http import JsonResponse
from rest_framework.response import Response


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
