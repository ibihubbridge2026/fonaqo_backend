from rest_framework.renderers import JSONRenderer


class StandardizedJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get("response") if renderer_context else None
        success = bool(response and 200 <= response.status_code < 400)

        if isinstance(data, dict) and {"status", "message", "data", "errors"}.issubset(data.keys()):
            payload = data
        else:
            message = "Request successful" if success else "Request failed"
            errors = {}
            wrapped_data = data if success else {}

            if isinstance(data, dict):
                if "message" in data and isinstance(data.get("message"), str):
                    message = data["message"]
                elif "detail" in data and isinstance(data.get("detail"), str):
                    message = data["detail"]

                if not success:
                    errors = data

            payload = {
                "status": "success" if success else "error",
                "message": message,
                "data": wrapped_data if success else {},
                "errors": errors if not success else {},
            }

        return super().render(payload, accepted_media_type, renderer_context)
