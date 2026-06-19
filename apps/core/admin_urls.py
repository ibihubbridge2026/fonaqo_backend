from django.urls import path

from . import admin_views

portal_patterns = [
    path('login/', admin_views.AdminPortalLoginView.as_view(), name='admin-portal-login'),
    path('logout/', admin_views.AdminLogoutView.as_view(), name='admin-portal-logout'),
    path('', admin_views.staff_login_redirect, name='admin-portal-home'),
]

dashboard_patterns = [
    path('', admin_views.AdminDashboardView.as_view(), name='admin-dashboard'),
    path('users/', admin_views.AdminUsersView.as_view(), name='admin-users'),
    path('users/agents/', admin_views.AdminAgentsView.as_view(), name='admin-agents'),
    path('users/clients/', admin_views.AdminClientsView.as_view(), name='admin-clients'),
    path('artisans/', admin_views.AdminArtisansView.as_view(), name='admin-artisans'),
    path('missions/', admin_views.AdminMissionsView.as_view(), name='admin-missions'),
    path('operations/', admin_views.AdminOperationsView.as_view(), name='admin-operations'),
    path('transactions/', admin_views.AdminTransactionsView.as_view(), name='admin-transactions'),
    path('wallet/', admin_views.AdminWalletView.as_view(), name='admin-wallet'),
    path('config/', admin_views.AdminConfigView.as_view(), name='admin-config'),
    path('boosts/', admin_views.AdminBoostsView.as_view(), name='admin-boosts'),
    path('influenceurs/', admin_views.AdminInfluencersView.as_view(), name='admin-influencers'),
    path('influenceurs/<int:influencer_id>/', admin_views.AdminInfluencerDetailView.as_view(), name='admin-influencer-detail'),
    path('influenceur/', admin_views.InfluencerPortalView.as_view(), name='admin-influencer-portal'),
    path('mon-profil/', admin_views.AdminProfileView.as_view(), name='admin-profile'),
    path('staff/', admin_views.AdminStaffView.as_view(), name='admin-staff'),
    path('audit/', admin_views.AdminAuditView.as_view(), name='admin-audit'),
    path('password-resets/', admin_views.AdminPasswordResetsView.as_view(), name='admin-password-resets'),
]
