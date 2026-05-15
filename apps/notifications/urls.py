from django.urls import path
from .views import RegisterDeviceView, notification_list_view, mark_notification_read_view

urlpatterns = [
    path('', notification_list_view, name='notification-list'),
    path('register-device/', RegisterDeviceView.as_view(), name='register_fcm_device'),
    path('<uuid:notification_id>/mark-read/', mark_notification_read_view, name='mark-notification-read'),
]