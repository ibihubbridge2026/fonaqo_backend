from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'listings', views.LocalListingViewSet, basename='leboncoin-listings')

urlpatterns = [
    path('', include(router.urls)),
]
