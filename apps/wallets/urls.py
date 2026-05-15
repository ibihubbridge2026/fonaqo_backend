from django.urls import path

from .views import wallet_balance_view, wallet_transactions_view

urlpatterns = [
    path('balance/', wallet_balance_view, name='wallet-balance'),
    path('transactions/', wallet_transactions_view, name='wallet-transactions'),
]