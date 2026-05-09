from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MissionViewSet

router = DefaultRouter()
router.register(r'missions', MissionViewSet)

urlpatterns = [
    path('', include(router.urls)),
]