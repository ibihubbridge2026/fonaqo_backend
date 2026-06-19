"""Permissions BackOffice FONAQO — Super Admin, Gestionnaire, Influenceur portail."""

from django.http import HttpResponseForbidden


MANAGER_NAV = frozenset({
    'dashboard',
    'agents',
    'clients',
    'missions',
    'transactions',
    'influencers',
    'operations',
    'profile',
})

SUPER_ADMIN_ONLY_NAV = frozenset({
    'artisans',
    'wallet',
    'boosts',
    'config',
    'staff',
    'audit',
    'password_resets',
})

INFLUENCER_PORTAL_NAV = frozenset({'influencer_portal'})


def get_influencer_for_user(user):
    if not user.is_authenticated:
        return None
    inf = getattr(user, 'influencer_portal', None)
    if inf is not None:
        return inf
    try:
        from apps.accounts.models import Influencer
        return Influencer.objects.filter(portal_user=user).first()
    except Exception:
        return None


def is_influencer_portal_user(user) -> bool:
    return get_influencer_for_user(user) is not None


def is_super_admin(user) -> bool:
    return bool(user.is_authenticated and user.is_superuser)


def is_manager(user) -> bool:
    return bool(
        user.is_authenticated
        and user.is_staff
        and not user.is_superuser
        and not is_influencer_portal_user(user)
    )


def can_access_nav(user, nav: str) -> bool:
    if not user.is_authenticated:
        return False
    if is_influencer_portal_user(user):
        return nav in INFLUENCER_PORTAL_NAV
    if not (user.is_staff or user.is_superuser):
        return False
    if is_super_admin(user):
        return True
    return nav in MANAGER_NAV


def staff_nav_context(user) -> dict:
    inf = get_influencer_for_user(user)
    if inf:
        return {
            'is_super_admin': False,
            'is_manager': False,
            'is_influencer_portal': True,
            'staff_role_label': 'Influenceur',
            'influencer_portal_id': inf.id,
        }
    return {
        'is_super_admin': is_super_admin(user),
        'is_manager': is_manager(user),
        'is_influencer_portal': False,
        'staff_role_label': 'Super Admin' if is_super_admin(user) else 'Gestionnaire',
    }


def deny_if_no_access(user, nav: str):
    if not can_access_nav(user, nav):
        return HttpResponseForbidden('Accès refusé pour votre rôle.')
    return None
