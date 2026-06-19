from django.urls import path

from . import kyc_views, staff_views

urlpatterns = [
    # KYC
    path('kyc/queue/', kyc_views.kyc_queue, name='staff-kyc-queue'),
    path('kyc/<int:profile_id>/approve/', kyc_views.kyc_approve, name='staff-kyc-approve'),
    path('kyc/<int:profile_id>/reject/', kyc_views.kyc_reject, name='staff-kyc-reject'),
    # Dashboard & config
    path('dashboard/kpis/', staff_views.dashboard_kpis, name='staff-dashboard-kpis'),
    path('dashboard/activity/', staff_views.dashboard_activity, name='staff-dashboard-activity'),
    path(
        'dashboard/recent-missions/',
        staff_views.dashboard_recent_missions,
        name='staff-dashboard-recent-missions',
    ),
    path('platform-config/', staff_views.platform_config, name='staff-platform-config'),
    # Payouts
    path('payouts/pending/', staff_views.payouts_pending, name='staff-payouts-pending'),
    path('payouts/<uuid:payout_id>/approve/', staff_views.payout_approve, name='staff-payout-approve'),
    path('payouts/<uuid:payout_id>/reject/', staff_views.payout_reject, name='staff-payout-reject'),
    # Escrow / litiges
    path('escrow/disputed/', staff_views.escrow_disputed, name='staff-escrow-disputed'),
    # Missions
    path('missions/<uuid:mission_id>/assign/', staff_views.mission_assign, name='staff-mission-assign'),
    path(
        'missions/<uuid:mission_id>/force-cancel/',
        staff_views.mission_force_cancel,
        name='staff-mission-force-cancel',
    ),
    # Utilisateurs
    path(
        'users/<uuid:user_id>/promote-artisan/',
        staff_views.promote_artisan,
        name='staff-promote-artisan',
    ),
    # Audit
    path('audit-log/', staff_views.audit_log, name='staff-audit-log'),
    # Influenceurs
    path('influencers/', staff_views.influencers_list_create, name='staff-influencers'),
    path(
        'influencers/<int:influencer_id>/',
        staff_views.influencer_update,
        name='staff-influencer-update',
    ),
    path(
        'influencers/<int:influencer_id>/payout/',
        staff_views.influencer_payout,
        name='staff-influencer-payout',
    ),
    path(
        'influencers/<int:influencer_id>/detail/',
        staff_views.influencer_detail,
        name='staff-influencer-detail',
    ),
    path(
        'influencers/<int:influencer_id>/withdrawals/',
        staff_views.influencer_withdrawal_request,
        name='staff-influencer-withdrawal-request',
    ),
    path(
        'influencers/<int:influencer_id>/portal-user/',
        staff_views.influencer_link_portal_user,
        name='staff-influencer-portal-link',
    ),
    path(
        'influencer-withdrawals/<int:withdrawal_id>/approve/',
        staff_views.influencer_withdrawal_approve,
        name='staff-influencer-withdrawal-approve',
    ),
    path(
        'influencer-withdrawals/<int:withdrawal_id>/reject/',
        staff_views.influencer_withdrawal_reject,
        name='staff-influencer-withdrawal-reject',
    ),
    # Boosts
    path(
        'boosts/plans/<int:plan_id>/',
        staff_views.boost_plan_update,
        name='staff-boost-plan-update',
    ),
    path(
        'boosts/<int:boost_id>/cancel/',
        staff_views.boost_cancel,
        name='staff-boost-cancel',
    ),
    path('wallet/summary/', staff_views.platform_wallet_summary, name='staff-wallet-summary'),
    path('artisans/', staff_views.artisan_create, name='staff-artisan-create'),
    path('artisans/<uuid:listing_id>/revoke/', staff_views.artisan_revoke, name='staff-artisan-revoke'),
    path('agents/<int:profile_id>/toggle-internal/', staff_views.agent_toggle_internal, name='staff-agent-toggle-internal'),
    path('badges/queue/', staff_views.badge_queue, name='staff-badge-queue'),
    path('badges/<int:profile_id>/approve/', staff_views.badge_approve, name='staff-badge-approve'),
    path('badges/<int:profile_id>/reject/', staff_views.badge_reject, name='staff-badge-reject'),
    path('staff-users/', staff_views.staff_users, name='staff-users'),
    path('me/', staff_views.staff_me, name='staff-me'),
    path('me/password/', staff_views.staff_change_password, name='staff-change-password'),
    path('users/<uuid:user_id>/suspend/', staff_views.user_suspend, name='staff-user-suspend'),
    path('users/<uuid:user_id>/reactivate/', staff_views.user_reactivate, name='staff-user-reactivate'),
    path('password-resets/', staff_views.password_reset_queue, name='staff-password-resets'),
    path(
        'password-resets/<int:request_id>/process/',
        staff_views.password_reset_process,
        name='staff-password-reset-process',
    ),
]
