from rest_framework import status
from rest_framework.response import Response


def build_envelope(success, message, data=None, errors=None):
    return {
        "status": "success" if success else "error",
        "message": message,
        "data": data if success else {},
        "errors": errors if not success else {},
    }


def success_response(data=None, message="Request successful", http_status=status.HTTP_200_OK):
    return Response(build_envelope(True, message, data=data), status=http_status)


def error_response(message="Request failed", errors=None, http_status=status.HTTP_400_BAD_REQUEST):
    return Response(build_envelope(False, message, errors=errors or {}), status=http_status)
