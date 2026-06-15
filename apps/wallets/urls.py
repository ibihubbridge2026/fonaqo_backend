from django.urls import path

from .views import (
    wallet_balance_view,
    wallet_deposit_view,
    wallet_transactions_view,
    wallet_withdraw_view,
)

urlpatterns = [
    path('balance/', wallet_balance_view, name='wallet-balance'),
    path('transactions/', wallet_transactions_view, name='wallet-transactions'),
    path('deposit/', wallet_deposit_view, name='wallet-deposit'),
    path('withdraw/', wallet_withdraw_view, name='wallet-withdraw'),
]