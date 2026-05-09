from rest_framework.views import exception_handler


def standardized_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    detail = response.data.get("detail") if isinstance(response.data, dict) else None
    message = detail if isinstance(detail, str) else "Request failed"

    response.data = {
        "status": "error",
        "message": message,
        "data": {},
        "errors": response.data if isinstance(response.data, dict) else {"detail": response.data},
    }
    return response
