from django.urls import path

from .views import public_artisan_detail_view, public_artisans_list_view

urlpatterns = [
    path('artisans/', public_artisans_list_view, name='public-artisans-list'),
    path('artisans/<uuid:artisan_id>/', public_artisan_detail_view, name='public-artisan-detail'),
]
