from django.urls import path

from .views import (
    wallet_balance_view,
    wallet_deposit_view,
    wallet_export_csv_view,
    wallet_export_pdf_view,
    wallet_transactions_view,
    wallet_withdraw_view,
    feexpay_payment_status_view,
)

urlpatterns = [
    path('balance/', wallet_balance_view, name='wallet-balance'),
    path('transactions/', wallet_transactions_view, name='wallet-transactions'),
    path('deposit/', wallet_deposit_view, name='wallet-deposit'),
    path('withdraw/', wallet_withdraw_view, name='wallet-withdraw'),
    path('payment-status/<str:reference>/', feexpay_payment_status_view, name='feexpay-payment-status'),
    path('export/pdf/', wallet_export_pdf_view, name='wallet-export-pdf'),
    path('export/csv/', wallet_export_csv_view, name='wallet-export-csv'),
]