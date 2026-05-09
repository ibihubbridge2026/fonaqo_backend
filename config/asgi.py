import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import apps.chat.routing
import apps.missions.routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

combined_urlpatterns = apps.chat.routing.websocket_urlpatterns + apps.missions.routing.websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(combined_urlpatterns)
    ),
})