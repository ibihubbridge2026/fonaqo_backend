"""Authentification JWT pour les WebSockets (query ?token=)."""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def _user_from_jwt(raw_token: str):
    if not raw_token:
        return AnonymousUser()
    try:
        from rest_framework_simplejwt.authentication import JWTAuthentication

        auth = JWTAuthentication()
        validated = auth.get_validated_token(raw_token)
        return auth.get_user(validated)
    except Exception:
        return AnonymousUser()


class JwtWsAuthMiddleware(BaseMiddleware):
    """Renseigne scope['user'] depuis ?token= (même JWT que l’API REST)."""

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        if scope.get("type") == "websocket":
            scope.setdefault("user", AnonymousUser())
            qs = parse_qs(scope.get("query_string", b"").decode())
            token = (qs.get("token") or [None])[0]
            if token:
                user = await _user_from_jwt(token)
                if user.is_authenticated:
                    scope["user"] = user
        return await self.inner(scope, receive, send)
