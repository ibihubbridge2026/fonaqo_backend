from django.urls import path

from apps.missions import public_views

from .views import public_artisan_detail_view, public_artisans_list_view, referral_join_preview

urlpatterns = [
    path('artisans/', public_artisans_list_view, name='public-artisans-list'),
    path('artisans/<uuid:artisan_id>/', public_artisan_detail_view, name='public-artisan-detail'),
    path('join/<slug:referral_slug>/', referral_join_preview, name='referral-join-preview'),
    path('missions/guest-create/', public_views.guest_mission_create, name='public-guest-mission-create'),
    path('mission-track/', public_views.public_mission_track, name='public-mission-track-api'),
    path('payments/guest-confirm/', public_views.guest_payment_confirm, name='public-guest-payment-confirm'),
]
