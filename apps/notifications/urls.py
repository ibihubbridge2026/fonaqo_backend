from django.urls import path
from .views import RegisterDeviceView, notification_list_view, mark_notification_read_view, mark_all_notifications_read_view, unread_count_view

urlpatterns = [
    path('', notification_list_view, name='notification-list'),
    path('register-device/', RegisterDeviceView.as_view(), name='register_fcm_device'),
    path('<uuid:notification_id>/mark-read/', mark_notification_read_view, name='mark-notification-read'),
    path('<uuid:notification_id>/read/', mark_notification_read_view, name='mark-notification-read-alias'),
    path('mark-all-read/', mark_all_notifications_read_view, name='mark-all-notifications-read'),
    path('unread-count/', unread_count_view, name='unread-count'),
]