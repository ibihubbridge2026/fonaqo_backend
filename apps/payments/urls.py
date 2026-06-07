from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WithdrawalViewSet

router = DefaultRouter()
router.register(r'withdraw', WithdrawalViewSet, basename='withdrawal')

urlpatterns = [
    path('', include(router.urls)),
]