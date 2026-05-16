from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    login_view,
    register_view,
    forgot_password_view,
    google_auth_view,
    profile_view,
    agent_suggestions_view,
    change_password_view,
    update_phone_view,
    agent_status_view,
)

urlpatterns = [
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('forgot-password/', forgot_password_view, name='forgot-password'),
    path('google-auth/', google_auth_view, name='google-auth'),
    path('profile/', profile_view, name='profile'),
    path('agents/suggestions/', agent_suggestions_view, name='agent-suggestions'),
    path('password/change/', change_password_view, name='password-change'),
    path('update-phone/', update_phone_view, name='update-phone'),
    path('agent/status/', agent_status_view, name='agent-status'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
]