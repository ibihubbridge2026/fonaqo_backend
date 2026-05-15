from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'', views.DisputeViewSet, basename='disputes')
router.register(r'evidences', views.DisputeEvidenceViewSet, basename='dispute-evidences')

urlpatterns = [
    path('', include(router.urls)),
]
