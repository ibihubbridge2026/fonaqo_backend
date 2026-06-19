from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DisputeViewSet

router = DefaultRouter()
router.register(r'', DisputeViewSet, basename='dispute')

urlpatterns = [
  path('', include(router.urls)),
]
