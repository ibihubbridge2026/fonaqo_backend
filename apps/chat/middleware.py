from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.db import close_old_connections
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

User = get_user_model()

class JwtWsAuthMiddleware(BaseMiddleware):
    """
    Middleware pour authentifier les connexions WebSocket avec JWT
    """
    
    async def __call__(self, scope, receive, send):
        # Fermer les anciennes connexions à la base de données
        close_old_connections()
        
        # Extraire le token du query string ou des headers
        token = self.get_token_from_scope(scope)
        
        if token:
            user = await self.get_user_from_token(token)
            scope['user'] = user if user else AnonymousUser()
        else:
            scope['user'] = AnonymousUser()
        
        return await super().__call__(scope, receive, send)
    
    def get_token_from_scope(self, scope):
        """Extraire le token du scope WebSocket"""
        # Essayer de récupérer depuis les headers
        headers = dict(scope.get('headers', []))
        auth_header = headers.get(b'authorization', b'').decode('utf-8')
        
        if auth_header.startswith('Bearer '):
            return auth_header[7:]
        
        # Essayer de récupérer depuis le query string
        query_string = scope.get('query_string', b'').decode('utf-8')
        if 'token=' in query_string:
            params = dict(param.split('=') for param in query_string.split('&') if '=' in param)
            return params.get('token')
        
        return None
    
    @database_sync_to_async
    def get_user_from_token(self, token):
        """Authentifier l'utilisateur à partir du token JWT (simplejwt)"""
        try:
            validated = UntypedToken(token)
            user_id = validated.payload.get('user_id')
            if user_id:
                return User.objects.get(id=user_id)
        except (InvalidToken, TokenError, User.DoesNotExist):
            pass
        return None
