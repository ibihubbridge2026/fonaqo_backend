from django.urls import path

from . import views

urlpatterns = [
    path('platform-fees/', views.platform_fees, name='platform-fees'),
    path('admin-notifications/', views.admin_notifications, name='admin-notifications'),
    path(
        'admin-notifications/<int:notification_id>/read/',
        views.admin_notification_mark_read,
        name='admin-notification-mark-read',
    ),
]
