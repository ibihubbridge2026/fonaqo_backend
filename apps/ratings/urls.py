"""URLs pour le système de notation."""

from django.urls import path
from .views import rate_mission_view

urlpatterns = [
    path('missions/<uuid:mission_id>/rate/', rate_mission_view, name='rate-mission'),
]
