from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OpportunityViewSet, OpportunityApplicationViewSet, OpportunityMatchViewSet

router = DefaultRouter()
router.register(r'opportunities', OpportunityViewSet, basename='opportunity')
router.register(r'applications', OpportunityApplicationViewSet, basename='opportunity-application')
router.register(r'matches', OpportunityMatchViewSet, basename='opportunity-match')

app_name = 'opportunities'

urlpatterns = [
    path('', include(router.urls)),
]
