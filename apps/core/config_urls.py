from django.urls import path

from . import config_views

urlpatterns = [
    path('support/', config_views.support_config, name='config-support'),
]
