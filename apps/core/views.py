from rest_framework.views import APIView

from .responses import error_response, success_response


class BaseAPIView(APIView):
    def success(self, data=None, message="Request successful", http_status=200):
        return success_response(data=data, message=message, http_status=http_status)

    def error(self, message="Request failed", errors=None, http_status=400):
        return error_response(message=message, errors=errors, http_status=http_status)
