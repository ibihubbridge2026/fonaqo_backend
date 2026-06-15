from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(
        r'ws/gps/(?P<mission_id>[0-9a-fA-F-]+)/$',
        consumers.GpsConsumer.as_asgi(),
    ),
    re_path(
        r'ws/timeline/(?P<mission_id>[0-9a-fA-F-]+)/$',
        consumers.TimelineConsumer.as_asgi(),
    ),
]
