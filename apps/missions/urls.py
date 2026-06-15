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
    path('assigned/', mv({'get': 'assigned'}), name='mission-assigned'),
    path('active/', mv({'get': 'active'}), name='mission-active'),
    path('history/', mv({'get': 'history'}), name='mission-history'),
    path('disputes/', mv({'get': 'disputes'}), name='mission-disputes'),
    # Vocal parsing endpoint
    path('parse-vocal/', views.parse_vocal_mission, name='mission-parse-vocal'),
    # Custom detail actions
    path('<uuid:pk>/accept/', mv({'post': 'accept'}), name='mission-accept'),
    path(
        '<uuid:pk>/decline_assignment/',
        mv({'post': 'decline_assignment'}),
        name='mission-decline-assignment',
    ),
    path('<uuid:pk>/start_mission/', mv({'post': 'start_mission'}), name='mission-start'),
    path('<uuid:pk>/mark_completed_live/', mv({'post': 'mark_completed_live'}), name='mission-complete'),
    path('<uuid:pk>/update_steps/', mv({'post': 'update_steps'}), name='mission-update-steps'),
    path('<uuid:pk>/submit_completion/', mv({'post': 'submit_completion'}), name='mission-submit'),
    path('<uuid:pk>/validate_completion/', mv({'post': 'validate_completion'}), name='mission-validate'),
    path('<uuid:pk>/open_dispute/', mv({'post': 'open_dispute'}), name='mission-dispute'),
    path('<uuid:pk>/cancel_mission/', mv({'post': 'cancel_mission'}), name='mission-cancel'),
    path('<uuid:pk>/update_negotiated_price/', mv({'post': 'update_negotiated_price'}), name='mission-update-negotiated-price'),
    path('<uuid:pk>/reject_negotiation/', mv({'post': 'reject_negotiation'}), name='mission-reject-negotiation'),
    path('<uuid:pk>/release_funds/', mv({'post': 'release_funds'}), name='mission-release-funds'),
    path('<uuid:pk>/manual_remote_validation/', mv({'post': 'manual_remote_validation'}), name='mission-manual-validation'),
    path('<uuid:pk>/rate_client/', mv({'post': 'rate_client'}), name='mission-rate-client'),
    path('<uuid:pk>/rate/', mv({'post': 'rate'}), name='mission-rate-agent'),
    path('<uuid:pk>/invoice/', mv({'get': 'invoice'}), name='mission-invoice'),
    # Standard CRUD
    path('<uuid:pk>/', mv({'get': 'retrieve'}), name='mission-detail'),
    path('', mv({'get': 'list', 'post': 'create'}), name='mission-list'),
    # Sub-resources (proofs, timeline, statistics)
    path('', include(router.urls)),
]
