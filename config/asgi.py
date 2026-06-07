import os
import django
from django.core.asgi import get_asgi_application

# 1. Définit les réglages
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# 2. INITIALISE DJANGO (C'est cette ligne qui manque ou qui est mal placée)
django.setup()

# 3. Récupère l'application HTTP
django_asgi_app = get_asgi_application()

# 4. IMPORTE LES ROUTINGS APRÈS L'INITIALISATION
from channels.routing import ProtocolTypeRouter, URLRouter

import apps.chat.routing
import apps.missions.routing
import apps.notifications.routing
from apps.chat.middleware import JwtWsAuthMiddleware

_ws_patterns = (
    apps.chat.routing.websocket_urlpatterns
    + apps.missions.routing.websocket_urlpatterns
    + apps.notifications.routing.websocket_urlpatterns
)

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JwtWsAuthMiddleware(
        URLRouter(_ws_patterns)
    ),
})