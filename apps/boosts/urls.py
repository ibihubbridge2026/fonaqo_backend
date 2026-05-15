from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'plans', views.BoostPlanViewSet, basename='boost-plans')
router.register(r'my-boosts', views.AgentBoostViewSet, basename='agent-boosts')

urlpatterns = [
    path('', include(router.urls)),
]
