from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from rest_framework.permissions import AllowAny, IsAdminUser

from apps.core.vitrine_views import (
    VitrineAgentPublicView,
    VitrineGuestCreateView,
    VitrineGuestTrackView,
)
from apps.core.admin_urls import dashboard_patterns, portal_patterns


# Regroupement des routes API pour une meilleure lisibilité
api_v1_patterns = [
    path('public/', include('apps.accounts.public_urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('missions/', include('apps.missions.urls')),
    path('wallets/', include('apps.wallets.urls')),
    path('payments/', include('apps.payments.urls')),
    path('escrow/', include('apps.escrow.urls')),
    path('services/', include('apps.services.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('chat/', include('apps.chat.urls')),
    path('ai/', include('apps.ai_search.urls')),
    path('opportunities/', include('apps.opportunities.urls')),
    path('boosts/', include('apps.boosts.urls')),
    path('disputes/', include('apps.disputes.urls')),
    path('statistics/', include('apps.statistics.urls')),
    path('leboncoin/', include('apps.leboncoin.urls')),
    path('ratings/', include('apps.ratings.urls')),
    path('core/', include('apps.core.api_urls')),
    path('config/', include('apps.core.config_urls')),
    path('staff/', include('apps.core.staff_urls')),
]

# V2 : même surface que v1 pour l'instant ; breaking changes futurs isolés ici.
api_v2_patterns = list(api_v1_patterns)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', include('apps.core.urls')),
    path('admin-portal/', include(portal_patterns)),
    path('admin-dashboard/', include(dashboard_patterns)),
    path('track/', VitrineGuestTrackView.as_view(), name='public-mission-track'),
    path('vitrine/creer-mission/', VitrineGuestCreateView.as_view(), name='vitrine-guest-create'),
    path('vitrine/suivi/', VitrineGuestTrackView.as_view(), name='vitrine-guest-track'),
    path('vitrine/agent/<uuid:agent_id>/', VitrineAgentPublicView.as_view(), name='vitrine-agent-public'),
    path('api/v1/', include(api_v1_patterns)),
    path('api/v2/', include(api_v2_patterns)),
]

# AUDIT FIX [P0] — Documentation API protégée hors DEBUG
if settings.DEBUG:
    urlpatterns += [
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    ]
else:
    urlpatterns += [
        path(
            'api/schema/',
            SpectacularAPIView.as_view(permission_classes=[IsAdminUser]),
            name='schema',
        ),
        path(
            'api/docs/',
            SpectacularSwaggerView.as_view(
                url_name='schema',
                permission_classes=[IsAdminUser],
            ),
            name='swagger-ui',
        ),
    ]

# Fichiers statiques : static/ live en DEBUG ; staticfiles/ collectés sinon (voir collectstatic au démarrage Docker)
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
else:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)