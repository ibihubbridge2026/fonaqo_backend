from django.urls import path
from .views import categories_list

urlpatterns = [
    path('categories/', categories_list, name='categories-list'),
    # Les routes seront ajoutées ici plus tard
]