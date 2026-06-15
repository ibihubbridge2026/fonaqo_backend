from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'conversations', views.ConversationViewSet, basename='conversations')
router.register(r'typing', views.TypingStatusViewSet, basename='typing-status')

urlpatterns = [
    path('', include(router.urls)),
    path('heartbeat/', views.heartbeat, name='chat-heartbeat'),
]
