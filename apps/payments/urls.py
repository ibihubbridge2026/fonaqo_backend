from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WithdrawalViewSet,
    feexpay_confirm_view,
    feexpay_init_view,
    feexpay_webhook_view,
)

router = DefaultRouter()
router.register(r'withdraw', WithdrawalViewSet, basename='withdrawal')

urlpatterns = [
    path('', include(router.urls)),
    path('feexpay/init/', feexpay_init_view, name='feexpay-init'),
    path('feexpay/confirm/', feexpay_confirm_view, name='feexpay-confirm'),
    path('feexpay/webhook/', feexpay_webhook_view, name='feexpay-webhook'),
]