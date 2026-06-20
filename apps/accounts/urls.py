from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    login_view,
    register_view,
    forgot_password_view,
    google_auth_view,
    profile_view,
    agent_suggestions_view,
    nearby_agents_view,
    favorites_list_view,
    favorites_detail_view,
    change_password_view,
    update_phone_view,
    agent_status_view,
    kyc_submit_view,
)
from .badge_views import (
    agent_badge_download_view,
    agent_badge_request_view,
    agent_badge_status_view,
)
from .favorites_views import (
    client_favorites_list_view,
    client_favorites_toggle_view,
)
from .ranking_views import top_agents_view
from .loyalty_views import client_rewards_view

urlpatterns = [
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('forgot-password/', forgot_password_view, name='forgot-password'),
    path('google-auth/', google_auth_view, name='google-auth'),
    path('profile/', profile_view, name='profile'),
    path('agents/suggestions/', agent_suggestions_view, name='agent-suggestions'),
    path('agents/nearby/', nearby_agents_view, name='nearby-agents'),
    path('favorites/', favorites_list_view, name='favorites-list'),
    path('favorites/<uuid:agent_id>/', favorites_detail_view, name='favorites-detail'),
    path('client/favorites/', client_favorites_list_view, name='client-favorites-list'),
    path('client/favorites/toggle/', client_favorites_toggle_view, name='client-favorites-toggle'),
    path('password/change/', change_password_view, name='password-change'),
    path('update-phone/', update_phone_view, name='update-phone'),
    path('agent/status/', agent_status_view, name='agent-status'),
    path('kyc/submit/', kyc_submit_view, name='kyc-submit'),
    path('agent/badge/', agent_badge_status_view, name='agent-badge-status'),
    path('agent/badge/request/', agent_badge_request_view, name='agent-badge-request'),
    path('agent/badge/download/', agent_badge_download_view, name='agent-badge-download'),
    path('agents/top/', top_agents_view, name='top-agents'),
    path('client/rewards/', client_rewards_view, name='client-rewards'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
]