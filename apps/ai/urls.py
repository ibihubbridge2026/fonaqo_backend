from django.urls import path

from . import views

urlpatterns = [
    path('assistant/', views.assistant_chat, name='ai-assistant'),
]
