from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'', views.OpportunityViewSet, basename='opportunity')

urlpatterns = [
    path('', include(router.urls)),
    path('list/', views.opportunities_list, name='opportunities-list'),
]
