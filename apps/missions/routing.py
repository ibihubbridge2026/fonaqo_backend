from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/missions/(?P<mission_id>[0-9a-f-]+)/$', consumers.MissionConsumer.as_asgi()),
    re_path(r'ws/gps/(?P<mission_id>[0-9a-f-]+)/$', consumers.MissionConsumer.as_asgi()),
]
