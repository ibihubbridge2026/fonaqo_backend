from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'proofs', views.MissionProofViewSet, basename='mission-proofs')
router.register(r'timeline', views.MissionTimelineEventViewSet, basename='mission-timeline')
router.register(r'statistics', views.AgentStatisticsViewSet, basename='agent-statistics')

urlpatterns = [
    path('', include(router.urls)),
]
