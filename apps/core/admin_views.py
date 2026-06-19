from datetime import timedelta

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.db.models import Count, Q, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .admin_permissions import (
    can_access_nav,
    get_influencer_for_user,
    is_influencer_portal_user,
    staff_nav_context,
)


def _is_portal_user(user):
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return is_influencer_portal_user(user)


def _is_staff_user(user):
    return _is_portal_user(user)


class StaffRequiredMixin(UserPassesTestMixin):
    login_url = '/admin-portal/login/'
    staff_nav = ''

    def test_func(self):
        return _is_portal_user(self.request.user)

    def dispatch(self, request, *args, **kwargs):
        if not self.test_func():
            return self.handle_no_permission()
        if is_influencer_portal_user(request.user):
            if self.staff_nav and self.staff_nav != 'influencer_portal':
                return redirect('admin-influencer-portal')
        elif self.staff_nav and not can_access_nav(request.user, self.staff_nav):
            return HttpResponseForbidden('Accès refusé pour votre rôle staff.')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(staff_nav_context(self.request.user))
        return ctx


class AdminPortalLoginView(LoginView):
    template_name = 'super_admin/admin_login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        if is_influencer_portal_user(self.request.user):
            return '/admin-dashboard/influenceur/'
        if _is_portal_user(self.request.user):
            return '/admin-dashboard/'
        return '/admin-portal/login/?error=not_staff'


class AdminLogoutView(View):
    def post(self, request):
        logout(request)
        return redirect('/admin-portal/login/')

    def get(self, request):
        logout(request)
        return redirect('/admin-portal/login/')


class AdminDashboardView(StaffRequiredMixin, TemplateView):
    template_name = 'super_admin/tableau_de_bord.html'
    staff_nav = 'dashboard'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({'active_nav': 'dashboard'})
        return ctx


class AdminAgentsView(StaffRequiredMixin, TemplateView):
    template_name = 'super_admin/gestion_agents.html'
    staff_nav = 'agents'

    def get_context_data(self, **kwargs):
        from apps.accounts.models import AgentProfile

        ctx = super().get_context_data(**kwargs)
        ctx['active_nav'] = 'agents'
        agents_qs = (
            AgentProfile.objects.select_related('user')
            .prefetch_related('user__offered_services')
            .filter(user__is_agent=True)
            .order_by('-updated_at')
        )
        ctx['agents'] = agents_qs[:100]
        ctx['stats'] = {
            'total': agents_qs.count(),
            'kyc_pending': agents_qs.filter(kyc_status__in=['SUBMITTED', 'PENDING']).count(),
            'kyc_approved': agents_qs.filter(kyc_status='APPROVED').count(),
            'online': agents_qs.filter(user__is_online=True).count(),
        }
        return ctx


class AdminClientsView(StaffRequiredMixin, TemplateView):
    template_name = 'super_admin/gestion_clients.html'
    staff_nav = 'clients'

    def get_context_data(self, **kwargs):
        from apps.accounts.models import ClientProfile

        ctx = super().get_context_data(**kwargs)
        ctx['active_nav'] = 'clients'
        clients_qs = ClientProfile.objects.select_related('user', 'influencer').order_by('-created_at')
        ctx['clients'] = clients_qs[:100]
        ctx['stats'] = {
            'total': clients_qs.count(),
            'with_referral': clients_qs.filter(influencer__isnull=False).count(),
            'this_month': clients_qs.filter(
                created_at__gte=timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0),
            ).count(),
        }
        return ctx


class AdminArtisansView(StaffRequiredMixin, TemplateView):
    template_name = 'super_admin/gestion_artisans.html'
    staff_nav = 'artisans'

    def get_context_data(self, **kwargs):
        from apps.leboncoin.models import LocalListing

        ctx = super().get_context_data(**kwargs)
        ctx['active_nav'] = 'artisans'
        artisans_qs = (
            LocalListing.objects.filter(
                category=LocalListing.Category.ARTISAN,
                is_active=True,
            )
            .order_by('-updated_at')
        )
        ctx['artisans'] = artisans_qs[:100]
        ctx['stats'] = {
            'total': artisans_qs.count(),
            'featured': artisans_qs.filter(is_featured=True).count(),
            'cities': artisans_qs.values('city').distinct().count(),
        }
        return ctx


class AdminUsersView(StaffRequiredMixin, View):
    """Redirection legacy → agents."""
    staff_nav = 'agents'

    def get(self, request):
        return redirect('admin-agents')


class AdminOperationsView(StaffRequiredMixin, TemplateView):
    template_name = 'super_admin/alertes.html'
    staff_nav = 'operations'

    def get_context_data(self, **kwargs):
        from apps.core.models import AdminNotification
        from apps.missions.models import Mission
        from django.contrib.auth import get_user_model

        User = get_user_model()
        ctx = super().get_context_data(**kwargs)
        ctx['active_nav'] = 'operations'
        five_min_ago = timezone.now() - timedelta(minutes=5)
        ctx['pending_alerts'] = AdminNotification.objects.filter(
            category=AdminNotification.Category.MISSION_UNASSIGNED,
            is_read=False,
        ).select_related('mission')[:20]
        ctx['stale_missions'] = Mission.objects.filter(
            status='PENDING',
            agent__isnull=True,
            created_at__lt=five_min_ago,
        ).select_related('client').order_by('created_at')[:20]
        ctx['agents_for_assign'] = User.objects.filter(
            is_agent=True, is_active=True,
        ).order_by('username')[:100]
        return ctx


class AdminTransactionsView(StaffRequiredMixin, TemplateView):
    template_name = 'super_admin/transactions.html'
    staff_nav = 'transactions'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['active_nav'] = 'transactions'
        from django.contrib.auth import get_user_model
        User = get_user_model()
        ctx['agents_for_assign'] = User.objects.filter(
            is_agent=True, is_active=True,
        ).order_by('username')[:100]
        return ctx


class AdminWalletView(StaffRequiredMixin, TemplateView):
    template_name = 'super_admin/wallet.html'
    staff_nav = 'wallet'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['active_nav'] = 'wallet'
        return ctx


class AdminConfigView(StaffRequiredMixin, TemplateView):
    template_name = 'super_admin/parametre.html'
    staff_nav = 'config'

    def get_context_data(self, **kwargs):
        from apps.boosts.models import BoostPlan

        ctx = super().get_context_data(**kwargs)
        ctx['active_nav'] = 'config'
        ctx['boost_plans'] = BoostPlan.objects.order_by('price')
        return ctx


class AdminBoostsView(StaffRequiredMixin, TemplateView):
    template_name = 'super_admin/gestion_boosts.html'
    staff_nav = 'boosts'

    def get_context_data(self, **kwargs):
        from apps.boosts.models import AgentBoost, BoostPlan

        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'active_nav': 'boosts',
            'plans': BoostPlan.objects.order_by('price'),
            'active_boosts': AgentBoost.objects.filter(
                status='active',
            ).select_related('agent', 'plan').order_by('-expires_at')[:50],
            'boost_history': AgentBoost.objects.exclude(
                status='active',
            ).select_related('agent', 'plan').order_by('-created_at')[:30],
        })
        return ctx


class AdminInfluencersView(StaffRequiredMixin, TemplateView):
    template_name = 'super_admin/gestion_influenceurs.html'
    staff_nav = 'influencers'

    def get_context_data(self, **kwargs):
        from apps.accounts.models import Influencer

        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'active_nav': 'influencers',
            'influencers': Influencer.objects.annotate(
                clients_count=Count('clients'),
            ).order_by('-created_at'),
        })
        return ctx


class AdminInfluencerDetailView(StaffRequiredMixin, TemplateView):
    template_name = 'super_admin/detail_influenceur.html'
    staff_nav = 'influencers'

    def get_context_data(self, **kwargs):
        from apps.accounts.models import Influencer

        ctx = super().get_context_data(**kwargs)
        inf = Influencer.objects.filter(pk=kwargs['influencer_id']).first()
        if not inf:
            from django.http import Http404
            raise Http404('Influenceur introuvable')
        ctx.update({
            'active_nav': 'influencers',
            'influencer': inf,
            'influencer_id': inf.id,
            'is_influencer_self': False,
            'can_admin_actions': True,
            'use_influencer_layout': False,
        })
        return ctx


class InfluencerPortalView(StaffRequiredMixin, TemplateView):
    """Portail influenceur — page unique sans sidebar."""
    template_name = 'super_admin/detail_influenceur.html'
    staff_nav = 'influencer_portal'

    def get_context_data(self, **kwargs):
        inf = get_influencer_for_user(self.request.user)
        if not inf:
            from django.http import Http404
            raise Http404('Compte influenceur non lié')
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'active_nav': 'influencer_portal',
            'influencer': inf,
            'influencer_id': inf.id,
            'is_influencer_self': True,
            'can_admin_actions': False,
            'use_influencer_layout': True,
        })
        return ctx


class AdminProfileView(StaffRequiredMixin, TemplateView):
    """Mon profil — accessible au staff (super admin + gestionnaire)."""
    template_name = 'super_admin/mon_profil.html'
    staff_nav = 'profile'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['active_nav'] = 'profile'
        ctx['use_influencer_layout'] = False
        return ctx


class AdminAuditView(StaffRequiredMixin, TemplateView):
    template_name = 'super_admin/audit_log.html'
    staff_nav = 'audit'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['active_nav'] = 'audit'
        return ctx


class AdminPasswordResetsView(StaffRequiredMixin, TemplateView):
    template_name = 'super_admin/password_resets.html'
    staff_nav = 'password_resets'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['active_nav'] = 'password_resets'
        return ctx


class AdminStaffView(StaffRequiredMixin, TemplateView):
    template_name = 'super_admin/gestion_staff.html'
    staff_nav = 'staff'

    def get_context_data(self, **kwargs):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        ctx = super().get_context_data(**kwargs)
        ctx['active_nav'] = 'staff'
        ctx['staff_users'] = User.objects.filter(
            Q(is_staff=True) | Q(is_superuser=True),
        ).order_by('-date_joined')[:50]
        return ctx


class AdminMissionsView(StaffRequiredMixin, TemplateView):
    template_name = 'super_admin/gestion_missions.html'
    staff_nav = 'missions'

    def get_context_data(self, **kwargs):
        from apps.missions.models import Mission
        from django.contrib.auth import get_user_model

        User = get_user_model()
        ctx = super().get_context_data(**kwargs)
        ctx['active_nav'] = 'missions'
        missions = (
            Mission.objects.select_related('client', 'agent', 'escrow')
            .prefetch_related('escrow_split_records__beneficiary_user')
            .order_by('-created_at')[:100]
        )
        cutoff = timezone.now() - timedelta(hours=24)
        ctx['ghost_missions'] = Mission.objects.filter(
            status='PENDING',
            agent__isnull=True,
            created_at__lt=cutoff,
        ).select_related('client').order_by('created_at')[:50]
        ctx['missions'] = missions
        ctx['agents_for_assign'] = User.objects.filter(
            is_agent=True, is_active=True,
        ).order_by('username')[:100]
        return ctx


@login_required
@user_passes_test(_is_staff_user)
def staff_login_redirect(request):
    return redirect('/admin-dashboard/')


@api_view(['GET'])
@permission_classes([AllowAny])
def public_mission_track_api(request):
    from apps.missions.public_views import public_mission_track
    return public_mission_track(request)
