from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.ai.views import assistant_chat

from .views import AISearchViewSet

router = DefaultRouter()
router.register(r'search', AISearchViewSet, basename='ai-search')

app_name = 'ai_search'

urlpatterns = [
    path('', include(router.urls)),
    path('assistant/', assistant_chat, name='ai-assistant'),
]
