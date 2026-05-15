from django.urls import path
from . import views

urlpatterns = [
    path('search-agents/', views.search_agents, name='search-agents'),
    path('search-missions/', views.search_missions, name='search-missions'),
]
