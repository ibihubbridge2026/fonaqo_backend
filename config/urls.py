from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView


# Regroupement des routes API pour une meilleure lisibilité
api_v1_patterns = [
    path('accounts/', include('apps.accounts.urls')),
    path('missions/', include('apps.missions.urls')),
    path('wallets/', include('apps.wallets.urls')),
    path('payments/', include('apps.payments.urls')),
    path('escrow/', include('apps.escrow.urls')),
    path('services/', include('apps.services.urls')),
    path('notifications/', include('apps.notifications.urls')),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    # Point d'entrée unique pour la V1
    path('api/v1/', include(api_v1_patterns)),
    
    # Documentation API
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

# Service des fichiers média et statiques en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)