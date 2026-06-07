from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'proofs', views.MissionProofViewSet, basename='mission-proofs')
router.register(r'timeline', views.MissionTimelineEventViewSet, basename='mission-timeline')
router.register(r'statistics', views.AgentStatisticsViewSet, basename='agent-statistics')

mv = views.MissionViewSet.as_view

urlpatterns = [
    # Custom list actions (must come before <uuid:pk>/ to avoid shadowing)
    path('available/', mv({'get': 'available'}), name='mission-available'),
    path('history/', mv({'get': 'history'}), name='mission-history'),
    # Vocal parsing endpoint
    path('parse-vocal/', views.parse_vocal_mission, name='mission-parse-vocal'),
    # Custom detail actions
    path('<uuid:pk>/accept/', mv({'post': 'accept'}), name='mission-accept'),
    path('<uuid:pk>/start_mission/', mv({'post': 'start_mission'}), name='mission-start'),
    path('<uuid:pk>/mark_completed_live/', mv({'post': 'mark_completed_live'}), name='mission-complete'),
    path('<uuid:pk>/update_steps/', mv({'post': 'update_steps'}), name='mission-update-steps'),
    path('<uuid:pk>/submit_completion/', mv({'post': 'submit_completion'}), name='mission-submit'),
    path('<uuid:pk>/validate_completion/', mv({'post': 'validate_completion'}), name='mission-validate'),
    path('<uuid:pk>/open_dispute/', mv({'post': 'open_dispute'}), name='mission-dispute'),
    # Standard CRUD
    path('<uuid:pk>/', mv({'get': 'retrieve'}), name='mission-detail'),
    path('', mv({'get': 'list', 'post': 'create'}), name='mission-list'),
    # Sub-resources (proofs, timeline, statistics)
    path('', include(router.urls)),
]
