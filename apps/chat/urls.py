from django.urls import path
from . import views

urlpatterns = [
    path('', views.message_list_view, name='message-list'),
    path('create/', views.message_create_view, name='message-create'),
    path('<uuid:message_id>/mark-read/', views.mark_message_read_view, name='mark-message-read'),
]
