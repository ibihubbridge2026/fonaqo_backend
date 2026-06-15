from django.urls import path

from . import kyc_views

urlpatterns = [
    path('kyc/queue/', kyc_views.kyc_queue, name='staff-kyc-queue'),
    path('kyc/<int:profile_id>/approve/', kyc_views.kyc_approve, name='staff-kyc-approve'),
    path('kyc/<int:profile_id>/reject/', kyc_views.kyc_reject, name='staff-kyc-reject'),
]
