from decimal import Decimal

from django.contrib.auth import get_user_model, update_session_auth_hash
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import BasePermission, IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.core.admin_audit import log_admin_action
from apps.core.choices import EscrowStatus, MissionStatus
from apps.core.models import AdminNotification, PlatformConfiguration
from apps.core.services import (
    AGENT_MISSION_DELAY_MINUTES_KEY,
    FEES_CONFIDENTIAL_KEY,
    FEES_URGENT_KEY,
    SPLIT_AGENT_PCT_KEY,
    SPLIT_INFLUENCER_PCT_KEY,
    SPLIT_PLATFORM_PCT_KEY,
    BOOST_PROMO_PERCENT_KEY,
    BOOST_PROMO_UNTIL_KEY,
    PlatformConfigService,
)

User = get_user_model()
_STAFF_AUTH = [SessionAuthentication, JWTAuthentication]


class IsBackofficeUser(BasePermission):
    """Staff Django ou compte portail influenceur."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff or request.user.is_superuser:
            return True
        from apps.accounts.models import Influencer
        return Influencer.objects.filter(portal_user=request.user).exists()


def _influencer_for_request(request, influencer_id):
    from apps.accounts.models import Influencer
    inf = get_object_or_404(Influencer, pk=influencer_id)
    if request.user.is_staff or request.user.is_superuser:
        return inf
    if inf.portal_user_id == request.user.id:
        return inf
    return None


def _build_influencer_detail(inf):
    from apps.accounts.models import ClientProfile, InfluencerWithdrawalRequest
    from apps.core.choices import MissionStatus
    from apps.escrow.models import EscrowSplitRecord
    from apps.missions.models import Mission

    bt = EscrowSplitRecord.BeneficiaryType.INFLUENCER
    total_earned = EscrowSplitRecord.objects.filter(
        influencer=inf, beneficiary_type=bt,
    ).aggregate(t=Sum('amount_fcfa'))['t'] or Decimal('0')

    total_withdrawn = InfluencerWithdrawalRequest.objects.filter(
        influencer=inf, status='APPROVED',
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    clients = []
    for cp in ClientProfile.objects.filter(influencer=inf).select_related('user'):
        user = cp.user
        completed = Mission.objects.filter(client=user, status=MissionStatus.COMPLETED)
        mission_count = completed.count()
        missions_amount = completed.aggregate(t=Sum('price'))['t'] or Decimal('0')
        infl_benefit = EscrowSplitRecord.objects.filter(
            influencer=inf,
            mission__client=user,
            beneficiary_type=bt,
        ).aggregate(t=Sum('amount_fcfa'))['t'] or Decimal('0')
        clients.append({
            'user_id': str(user.id),
            'name': user.get_full_name() or user.username,
            'phone': user.phone_number or '—',
            'linked_at': cp.influencer_linked_at.strftime('%Y-%m-%d') if cp.influencer_linked_at else '—',
            'missions_count': mission_count,
            'missions_amount': float(missions_amount),
            'influencer_benefit': float(infl_benefit),
        })

    withdrawals = []
    for w in InfluencerWithdrawalRequest.objects.filter(influencer=inf).order_by('-requested_at')[:30]:
        withdrawals.append({
            'id': w.id,
            'amount': float(w.amount),
            'status': w.status,
            'note': w.note,
            'admin_note': w.admin_note,
            'requested_at': w.requested_at.strftime('%Y-%m-%d %H:%M'),
            'processed_at': w.processed_at.strftime('%Y-%m-%d %H:%M') if w.processed_at else None,
            'proof_url': w.proof_file.url if w.proof_file else None,
        })

    start = inf.contract_start
    end = inf.contract_end
    return {
        'id': inf.id,
        'name': inf.name,
        'code_promo': inf.code_promo,
        'referral_slug': inf.referral_slug,
        'commission_rate': float(inf.commission_rate),
        'duration_years': inf.duration_years,
        'contract_start': start.isoformat() if start else None,
        'contract_end': end.isoformat() if end else None,
        'balance_current': float(inf.earnings_balance),
        'total_earned': float(total_earned),
        'total_withdrawn': float(total_withdrawn),
        'clients_count': len(clients),
        'clients': clients,
        'withdrawals': withdrawals,
        'deep_link': f'fonaco.app/join/{inf.referral_slug or inf.code_promo}',
    }


from apps.core.choices import MissionStatus
from apps.missions.status_policy import (
    AGENT_ACTIVE_MISSION_STATUSES,
    CLIENT_ONGOING_MISSION_STATUSES,
)

_ACTIVE_MISSION_STATUSES = [
    *CLIENT_ONGOING_MISSION_STATUSES,
    MissionStatus.DISPUTED,
]


def _err(message: str, code=status.HTTP_400_BAD_REQUEST):
    return Response({'message': message}, status=code)


def _revenue_split_percentages():
    """Répartition agent / plateforme / influenceur — toujours depuis la config plateforme."""
    agent_cfg = float(PlatformConfigService.get_decimal(SPLIT_AGENT_PCT_KEY, '88'))
    platform_cfg = float(PlatformConfigService.get_decimal(SPLIT_PLATFORM_PCT_KEY, '10'))
    influencer_cfg = float(PlatformConfigService.get_decimal(SPLIT_INFLUENCER_PCT_KEY, '2'))
    return {
        'agent_pct': agent_cfg,
        'platform_pct': platform_cfg,
        'influencer_pct': influencer_cfg,
        'configured': True,
    }


def _mission_public_ref(mission):
    if mission.tracking_code:
        return mission.tracking_code
    return f'FNC-{str(mission.id).replace("-", "")[:6].upper()}'


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def dashboard_kpis(request):
    from apps.escrow.models import Escrow, EscrowSplitRecord
    from apps.missions.models import Mission

    escrow_volume = Escrow.objects.filter(
        status__in=[EscrowStatus.HELD, EscrowStatus.DISPUTED],
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    active_missions = Mission.objects.filter(
        status__in=_ACTIVE_MISSION_STATUSES,
    ).count()

    agents_count = User.objects.filter(is_agent=True, is_active=True).count()

    platform_revenue = EscrowSplitRecord.objects.filter(
        beneficiary_type=EscrowSplitRecord.BeneficiaryType.PLATFORM,
    ).aggregate(total=Sum('amount_fcfa'))['total'] or Decimal('0')

    open_disputes = 0
    try:
        from apps.disputes.models import Dispute
        open_disputes = Dispute.objects.exclude(
            status__in=[Dispute.Status.RESOLVED, Dispute.Status.CLOSED],
        ).count()
    except Exception:
        pass

    pending_payouts = 0
    try:
        from apps.wallets.models import PayoutRequest
        from apps.core.choices import PayoutRequestStatus
        pending_payouts = PayoutRequest.objects.filter(
            status=PayoutRequestStatus.PENDING,
        ).count()
    except Exception:
        pass

    split = _revenue_split_percentages()
    return Response({
        'volume_escrow': float(escrow_volume),
        'active_missions': active_missions,
        'agents_count': agents_count,
        'platform_revenue': float(platform_revenue),
        'disputes_open': open_disputes,
        'payouts_pending': pending_payouts,
        'revenue_split': split,
        'split_agent': split['agent_pct'],
        'split_platform': split['platform_pct'],
        'split_influencer': split['influencer_pct'],
    })


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def dashboard_activity(request):
    """Flux activité live : notifications admin, audit, événements mission."""
    from apps.core.models import AdminAuditLog
    from apps.missions.models import MissionTimelineEvent

    limit = min(int(request.query_params.get('limit', 5)), 50)
    page = max(int(request.query_params.get('page', 1)), 1)
    items = []

    fetch_limit = min(max(limit * page, limit), 100)

    for notif in AdminNotification.objects.order_by('-created_at')[:fetch_limit]:
        items.append({
            'timestamp': notif.created_at.isoformat(),
            'time': notif.created_at.strftime('%H:%M'),
            'type': 'notification',
            'label': notif.title,
            'detail': (notif.message or '')[:140],
            'severity': notif.severity,
        })

    for entry in AdminAuditLog.objects.select_related('admin').order_by('-created_at')[:fetch_limit]:
        who = entry.admin.username if entry.admin_id else 'system'
        items.append({
            'timestamp': entry.created_at.isoformat(),
            'time': entry.created_at.strftime('%H:%M'),
            'type': 'audit',
            'label': entry.action.replace('_', ' '),
            'detail': entry.detail[:140] or f'{who} → {entry.target_type}:{entry.target_id}',
            'severity': 'info',
        })

    event_labels = dict(MissionTimelineEvent.EVENT_TYPE_CHOICES)
    for ev in MissionTimelineEvent.objects.select_related('mission', 'performed_by').order_by(
        '-occurred_at',
    )[:fetch_limit]:
        who = ''
        if ev.performed_by_id:
            who = ev.performed_by.username
        items.append({
            'timestamp': ev.occurred_at.isoformat(),
            'time': ev.occurred_at.strftime('%H:%M'),
            'type': 'mission',
            'label': event_labels.get(ev.event_type, ev.event_type),
            'detail': f'{_mission_public_ref(ev.mission)} — {ev.mission.title[:60]}'
            + (f' ({who})' if who else ''),
            'severity': 'warning' if ev.event_type == 'disputed' else 'info',
        })

    items.sort(key=lambda x: x['timestamp'], reverse=True)
    total = len(items)
    start = (page - 1) * limit
    page_items = items[start:start + limit]
    return Response({
        'results': page_items,
        'count': len(page_items),
        'total': total,
        'page': page,
        'page_size': limit,
        'has_more': start + limit < total,
    })


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def dashboard_recent_missions(request):
    from apps.missions.models import Mission

    limit = min(int(request.query_params.get('limit', 10)), 25)
    status_labels = dict(MissionStatus.choices)
    rows = []
    for m in Mission.objects.select_related('client', 'agent').order_by('-created_at')[:limit]:
        client_name = m.client.get_full_name() or m.client.username
        rows.append({
            'id': str(m.id),
            'ref': _mission_public_ref(m),
            'client': client_name,
            'amount': float(m.price),
            'status': m.status,
            'status_label': status_labels.get(m.status, m.status),
            'agent': m.agent.username if m.agent_id else None,
            'created_at': m.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    return Response({'results': rows, 'count': len(rows)})


@api_view(['GET', 'PATCH'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def platform_config(request):
    if request.method == 'GET':
        from apps.boosts.models import BoostPlan

        plans = []
        for p in BoostPlan.objects.order_by('price'):
            plans.append({
                'id': p.id,
                'name': p.name,
                'price': float(p.price),
                'price_fcfa': float(p.price),
                'duration_hours': p.duration_hours,
                'duration_days': p.duration_days,
                'visibility_multiplier': float(p.visibility_multiplier),
                'is_active': p.is_active,
                'description': p.description,
            })
        split = _revenue_split_percentages()
        return Response({
            'FEES_URGENT': str(PlatformConfigService.get_decimal(FEES_URGENT_KEY, '500')),
            'FEES_CONFIDENTIAL': str(
                PlatformConfigService.get_decimal(FEES_CONFIDENTIAL_KEY, '500'),
            ),
            'SPLIT_AGENT_PCT': str(PlatformConfigService.get_decimal(SPLIT_AGENT_PCT_KEY, '88')),
            'SPLIT_PLATFORM_PCT': str(PlatformConfigService.get_decimal(SPLIT_PLATFORM_PCT_KEY, '10')),
            'SPLIT_INFLUENCER_PCT': str(PlatformConfigService.get_decimal(SPLIT_INFLUENCER_PCT_KEY, '2')),
            'BOOST_PROMO_PERCENT': PlatformConfigService.get_raw(BOOST_PROMO_PERCENT_KEY, '0'),
            'BOOST_PROMO_UNTIL': PlatformConfigService.get_raw(BOOST_PROMO_UNTIL_KEY, ''),
            'AGENT_MISSION_DELAY_MINUTES': str(
                PlatformConfigService.agent_mission_delay_minutes(),
            ),
            'revenue_split': split,
            'boost_plans': plans,
        })

    payload = request.data
    updated = {}
    config_map = {
        'FEES_URGENT': (FEES_URGENT_KEY, 'Frais mission urgente (FCFA)'),
        'fees_urgent': (FEES_URGENT_KEY, 'Frais mission urgente (FCFA)'),
        'FEES_CONFIDENTIAL': (FEES_CONFIDENTIAL_KEY, 'Frais agent interne / confidentiel (FCFA)'),
        'fees_confidential': (FEES_CONFIDENTIAL_KEY, 'Frais agent interne / confidentiel (FCFA)'),
        'SPLIT_AGENT_PCT': (SPLIT_AGENT_PCT_KEY, 'Part agent escrow (%)'),
        'SPLIT_PLATFORM_PCT': (SPLIT_PLATFORM_PCT_KEY, 'Part plateforme escrow (%)'),
        'SPLIT_INFLUENCER_PCT': (SPLIT_INFLUENCER_PCT_KEY, 'Part influenceur escrow (%)'),
        'BOOST_PROMO_PERCENT': (BOOST_PROMO_PERCENT_KEY, 'Promo boost (%)'),
        'BOOST_PROMO_UNTIL': (BOOST_PROMO_UNTIL_KEY, 'Fin promo boost (ISO date)'),
        'AGENT_MISSION_DELAY_MINUTES': (
            AGENT_MISSION_DELAY_MINUTES_KEY,
            'Délai visibilité missions (minutes, agents non boost)',
        ),
    }

    # Validation des pourcentages de split escrow
    split_keys = ['SPLIT_AGENT_PCT', 'SPLIT_PLATFORM_PCT', 'SPLIT_INFLUENCER_PCT']
    split_values = {}
    for key in split_keys:
        if key in payload:
            try:
                split_values[key] = float(payload[key])
            except (ValueError, TypeError):
                return _err(f'Valeur invalide pour {key}: doit être un nombre', status.HTTP_400_BAD_REQUEST)

    if split_values:
        total_pct = sum(split_values.values())
        if abs(total_pct - 100.0) > 0.1:  # Tolérance de 0.1%
            return _err(
                f'La somme des pourcentages de split escrow doit être égale à 100% (actuel: {total_pct}%)',
                status.HTTP_400_BAD_REQUEST
            )

    for key, val in payload.items():
        if key not in config_map:
            continue
        cfg_key, desc = config_map[key]
        try:
            PlatformConfigService.set_value(cfg_key, val, desc)
            updated[cfg_key] = str(val)
        except Exception as e:
            return _err(f'Erreur lors de la persistance de {cfg_key}: {str(e)}', status.HTTP_400_BAD_REQUEST)

    if not updated:
        return _err(
            'Aucun paramètre reconnu (FEES_*, SPLIT_*_PCT, BOOST_PROMO_*).',
        )

    log_admin_action(
        request.user, 'PLATFORM_CONFIG_PATCH',
        target_type='PlatformConfiguration',
        detail=', '.join(f'{k}={v}' for k, v in updated.items()),
        metadata=updated,
    )
    return Response({'status': 'ok', 'updated': updated})


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def payouts_pending(request):
    from apps.core.choices import PayoutRequestStatus
    from apps.wallets.models import PayoutRequest

    qs = PayoutRequest.objects.filter(
        status=PayoutRequestStatus.PENDING,
    ).select_related('wallet__user__agent_profile__manager').order_by('-created_at')[:100]

    results = []
    for payout in qs:
        user = payout.wallet.user
        mgr = None
        try:
            mgr = user.agent_profile.manager
        except Exception:
            pass
        results.append({
            'id': str(payout.id),
            'amount': float(payout.amount),
            'status': payout.status,
            'username': user.username,
            'agent_name': user.get_full_name() or user.username,
            'user_id': str(user.id),
            'manager_name': mgr.name if mgr else None,
            'payment_method': payout.payment_method,
            'phone_number': payout.phone_number,
            'created_at': payout.created_at.isoformat(),
        })
    return Response({'results': results, 'count': len(results)})


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def payout_approve(request, payout_id):
    from apps.wallets.models import PayoutRequest
    from apps.wallets.payout_service import PayoutService, PayoutServiceError

    try:
        payout = PayoutRequest.objects.get(pk=payout_id)
    except PayoutRequest.DoesNotExist:
        return _err('Demande de retrait introuvable.', status.HTTP_404_NOT_FOUND)

    try:
        payout = PayoutService.approve(payout, admin_user=request.user)
    except PayoutServiceError as exc:
        return _err(str(exc), status.HTTP_400_BAD_REQUEST)

    log_admin_action(
        request.user, 'PAYOUT_APPROVE',
        target_type='PayoutRequest', target_id=payout_id,
        detail=(
            f'{payout.amount} FCFA → {payout.wallet.user.username} '
            f'(txn {payout.ledger_transaction_id})'
        ),
        metadata={'ledger_transaction_id': str(payout.ledger_transaction_id)},
    )
    return Response({
        'status': 'ok',
        'payout_id': str(payout.id),
        'payout_status': payout.status,
        'transaction_id': str(payout.ledger_transaction_id),
    })


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def payout_reject(request, payout_id):
    from apps.wallets.models import PayoutRequest
    from apps.wallets.payout_service import PayoutService, PayoutServiceError

    reason = (request.data.get('reason') or '').strip()

    try:
        payout = PayoutRequest.objects.get(pk=payout_id)
    except PayoutRequest.DoesNotExist:
        return _err('Demande de retrait introuvable.', status.HTTP_404_NOT_FOUND)

    try:
        payout = PayoutService.reject(
            payout, admin_user=request.user, reason=reason,
        )
    except PayoutServiceError as exc:
        return _err(str(exc), status.HTTP_400_BAD_REQUEST)

    log_admin_action(
        request.user, 'PAYOUT_REJECT',
        target_type='PayoutRequest', target_id=payout_id,
        detail=f'Rejet {payout.amount} FCFA — {reason or "sans motif"}',
    )
    return Response({
        'status': 'ok',
        'payout_id': str(payout.id),
        'payout_status': payout.status,
    })


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def escrow_disputed(request):
    from apps.disputes.models import Dispute

    qs = Dispute.objects.exclude(
        status__in=[Dispute.Status.RESOLVED, Dispute.Status.CLOSED],
    ).select_related(
        'mission__client', 'mission__agent__agent_profile__manager', 'mission__escrow',
    ).order_by('-created_at')[:100]

    results = []
    for d in qs:
        m = d.mission
        escrow = getattr(m, 'escrow', None)
        agent_manager = None
        if m.agent_id:
            try:
                agent_manager = m.agent.agent_profile.manager.name
            except Exception:
                pass
        results.append({
            'dispute_id': d.id,
            'mission_id': str(m.id),
            'mission_ref': str(m.id)[:8].upper(),
            'client': m.client.username or m.client.phone_number,
            'agent': m.agent.username if m.agent_id else None,
            'agent_manager': agent_manager,
            'amount': float(escrow.amount) if escrow else float(m.price or 0),
            'escrow_status': escrow.status if escrow else '—',
            'status': d.status,
            'title': d.title,
            'description': d.description,
            'opened_by': d.opened_by.username if d.opened_by_id else None,
        })
    return Response({'results': results, 'count': len(results)})


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def mission_assign(request, mission_id):
    from apps.missions.models import Mission, MissionTimelineEvent
    from apps.missions.views import _notify_mission_event

    agent_id = request.data.get('agent_id')
    if not agent_id:
        return _err('agent_id requis.')

    try:
        agent = User.objects.get(pk=agent_id, is_agent=True, is_active=True)
    except User.DoesNotExist:
        return _err('Agent introuvable.', status.HTTP_404_NOT_FOUND)

    try:
        with transaction.atomic():
            mission = Mission.objects.select_for_update().get(pk=mission_id)
            if mission.status != MissionStatus.PENDING or mission.agent_id is not None:
                return _err(
                    'Mission non assignable (déjà prise ou statut invalide).',
                    status.HTTP_409_CONFLICT,
                )
            mission.target_agent_username = agent.username
            mission.save(update_fields=['target_agent_username', 'updated_at'])
    except Mission.DoesNotExist:
        return _err('Mission introuvable.', status.HTTP_404_NOT_FOUND)

    MissionTimelineEvent.objects.create(
        mission=mission,
        event_type='assigned',
        performed_by=request.user,
        metadata={'assigned_agent_id': str(agent.id), 'assigned_by_staff': str(request.user.id)},
    )

    _notify_mission_event(
        agent,
        'Mission réservée pour vous',
        f'Le staff vous a assigné « {mission.title[:80]} » — acceptez-la dans Missions assignées.',
        'MISSION_ASSIGNED',
        mission.id,
    )
    _notify_mission_event(
        mission.client,
        'Agent désigné pour votre mission',
        f'Un agent a été désigné pour « {mission.title[:80]} ».',
        'MISSION_AGENT_ASSIGNED',
        mission.id,
    )

    AdminNotification.objects.filter(
        mission=mission,
        category=AdminNotification.Category.MISSION_UNASSIGNED,
        is_read=False,
    ).update(is_read=True)

    log_admin_action(
        request.user, 'MISSION_ASSIGN',
        target_type='Mission', target_id=mission_id,
        detail=f'Agent @{agent.username} (réservation)',
    )
    return Response({
        'status': 'ok',
        'mission_id': str(mission.id),
        'agent_id': str(agent.id),
        'target_agent_username': agent.username,
    })


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def mission_force_cancel(request, mission_id):
    from apps.escrow.services import EscrowService
    from apps.missions.models import Mission, MissionTimelineEvent

    reason = request.data.get('reason', 'Annulation forcée admin — mission fantôme PENDING > 24h')

    try:
        with transaction.atomic():
            mission = Mission.objects.select_for_update().get(pk=mission_id)
            if mission.status not in (MissionStatus.PENDING,):
                return _err('Seules les missions PENDING peuvent être annulées forcément.')
            if mission.agent_id is not None:
                return _err('Mission déjà assignée — utilisez le flux litige/annulation standard.')

            if hasattr(mission, 'escrow') and mission.escrow.status == EscrowStatus.HELD:
                EscrowService.refund_to_client(mission, reason=reason)

            mission.status = MissionStatus.CANCELLED
            mission.save(update_fields=['status', 'updated_at'])
    except Mission.DoesNotExist:
        return _err('Mission introuvable.', status.HTTP_404_NOT_FOUND)
    except ValueError as exc:
        return _err(str(exc))

    MissionTimelineEvent.objects.create(
        mission=mission,
        event_type='cancelled',
        performed_by=request.user,
        metadata={'force_cancel': True, 'reason': reason},
    )
    AdminNotification.objects.filter(mission=mission, is_read=False).update(is_read=True)

    log_admin_action(
        request.user, 'MISSION_FORCE_CANCEL',
        target_type='Mission', target_id=mission_id,
        detail=reason,
    )
    return Response({'status': 'ok', 'mission_id': str(mission.id)})


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def promote_artisan(request, user_id):
    """Publie un agent terrain dans l'annuaire LeBonCoin (artisan expert)."""
    from apps.leboncoin.models import LocalListing

    try:
        user = User.objects.get(pk=user_id, is_agent=True)
    except User.DoesNotExist:
        return _err('Agent introuvable.', status.HTTP_404_NOT_FOUND)

    specialty = user.service_domain or user.expertises or 'Artisan expert'
    listing, created = LocalListing.objects.get_or_create(
        name=user.get_full_name() or user.username,
        phone=user.phone_number or '',
        defaults={
            'category': LocalListing.Category.ARTISAN,
            'specialty': specialty[:120],
            'description': f'Agent FONACO promu artisan — @{user.username}',
            'city': user.city or 'Cotonou',
            'district': user.address or '',
            'email': user.email or '',
            'is_active': True,
        },
    )
    if not created:
        listing.is_active = True
        listing.save(update_fields=['is_active', 'updated_at'])

    log_admin_action(
        request.user, 'PROMOTE_ARTISAN',
        target_type='LocalListing', target_id=str(listing.id),
        detail=f'@{user.username} → annuaire LeBonCoin',
    )
    return Response({
        'status': 'ok',
        'user_id': str(user.id),
        'listing_id': str(listing.id),
    })


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def audit_log(request):
    from apps.core.models import AdminAuditLog

    limit = min(int(request.query_params.get('limit', 100)), 500)
    action_filter = request.query_params.get('action', '').strip()

    qs = AdminAuditLog.objects.select_related('admin').order_by('-created_at')
    if action_filter:
        qs = qs.filter(action__icontains=action_filter)

    rows = []
    for entry in qs[:limit]:
        rows.append({
            'id': entry.id,
            'created_at': entry.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'admin_username': entry.admin.username if entry.admin_id else 'system',
            'action': entry.action,
            'target': f'{entry.target_type}:{entry.target_id}' if entry.target_type else '—',
            'detail': entry.detail,
            'metadata': entry.metadata,
        })
    return Response({'results': rows, 'count': len(rows)})


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def admin_notifications_list(request):
    """Alertes opérationnelles staff (ledger, litiges, sécurité…)."""
    from apps.core.models import AdminNotification

    limit = min(int(request.query_params.get('limit', 50)), 200)
    unread_only = request.query_params.get('unread') == '1'
    severity = request.query_params.get('severity', '').strip()
    category = request.query_params.get('category', '').strip()

    qs = AdminNotification.objects.order_by('-created_at')
    if unread_only:
        qs = qs.filter(is_read=False)
    if severity:
        qs = qs.filter(severity=severity)
    if category:
        qs = qs.filter(category=category)

    rows = []
    for n in qs[:limit]:
        rows.append({
            'id': n.id,
            'category': n.category,
            'severity': n.severity,
            'title': n.title,
            'message': n.message,
            'is_read': n.is_read,
            'metadata': n.metadata,
            'mission_id': str(n.mission_id) if n.mission_id else None,
            'created_at': n.created_at.isoformat(),
        })

    unread_count = AdminNotification.objects.filter(is_read=False).count()
    return Response({
        'results': rows,
        'count': len(rows),
        'unread_count': unread_count,
    })


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def admin_notifications_unread_count(request):
    from apps.core.models import AdminNotification

    return Response({
        'unread_count': AdminNotification.objects.filter(is_read=False).count(),
    })


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def admin_notification_mark_read(request, notification_id):
    from apps.core.models import AdminNotification

    notification = get_object_or_404(AdminNotification, pk=notification_id)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])
    return Response({'id': notification.id, 'is_read': True})


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def admin_notifications_mark_all_read(request):
    from apps.core.models import AdminNotification

    updated = AdminNotification.objects.filter(is_read=False).update(is_read=True)
    return Response({'marked_read': updated})


# --- Influenceurs ---

@api_view(['GET', 'POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def influencers_list_create(request):
    from apps.accounts.models import Influencer

    if request.method == 'GET':
        results = []
        for inf in Influencer.objects.annotate(
            clients_count=Count('clients'),
        ).order_by('-created_at'):
            results.append({
                'id': inf.id,
                'name': inf.name,
                'code_promo': inf.code_promo,
                'referral_slug': inf.referral_slug,
                'commission_rate': float(inf.commission_rate),
                'earnings_balance': float(inf.earnings_balance),
                'clients_count': inf.clients_count,
            })
        return Response({'results': results})

    name = (request.data.get('name') or '').strip()
    code_promo = (request.data.get('code_promo') or '').strip().upper()
    if not name or not code_promo:
        return _err('name et code_promo requis.')

    if Influencer.objects.filter(code_promo=code_promo).exists():
        return _err('Ce code promo existe déjà.', status.HTTP_409_CONFLICT)

    inf = Influencer.objects.create(
        name=name,
        code_promo=code_promo,
        commission_rate=Decimal(str(request.data.get('commission_rate', '0.02'))),
        duration_years=int(request.data.get('duration_years', 2)),
        referral_slug=(request.data.get('referral_slug') or '').strip() or None,
    )
    log_admin_action(
        request.user, 'INFLUENCER_CREATE',
        target_type='Influencer', target_id=inf.id,
        detail=f'{inf.name} ({inf.code_promo})',
    )
    return Response({'status': 'ok', 'id': inf.id}, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def influencer_update(request, influencer_id):
    from apps.accounts.models import Influencer

    inf = get_object_or_404(Influencer, pk=influencer_id)
    fields = []
    for field in ('name', 'code_promo', 'referral_slug'):
        if field in request.data:
            setattr(inf, field, request.data[field])
            fields.append(field)
    if 'commission_rate' in request.data:
        inf.commission_rate = Decimal(str(request.data['commission_rate']))
        fields.append('commission_rate')
    if 'duration_years' in request.data:
        inf.duration_years = int(request.data['duration_years'])
        fields.append('duration_years')
    if fields:
        inf.save()

    log_admin_action(
        request.user, 'INFLUENCER_UPDATE',
        target_type='Influencer', target_id=influencer_id,
        detail=', '.join(fields),
    )
    return Response({'status': 'ok', 'id': inf.id})


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def influencer_payout(request, influencer_id):
    from apps.accounts.models import Influencer

    inf = get_object_or_404(Influencer, pk=influencer_id)
    raw = request.data.get('amount')
    amount = Decimal(str(raw)) if raw is not None else inf.earnings_balance

    if amount <= 0:
        return _err('Montant invalide.')
    if inf.earnings_balance < amount:
        return _err('Solde commissions insuffisant.')

    inf.earnings_balance -= amount
    inf.save(update_fields=['earnings_balance'])

    log_admin_action(
        request.user, 'INFLUENCER_PAYOUT',
        target_type='Influencer', target_id=influencer_id,
        detail=f'Versement {amount} FCFA',
        metadata={'amount': float(amount)},
    )
    return Response({
        'status': 'ok',
        'paid_amount': float(amount),
        'remaining_balance': float(inf.earnings_balance),
    })


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsBackofficeUser])
def influencer_detail(request, influencer_id):
    inf = _influencer_for_request(request, influencer_id)
    if not inf:
        return _err('Accès refusé.', status.HTTP_403_FORBIDDEN)
    return Response(_build_influencer_detail(inf))


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsBackofficeUser])
def influencer_withdrawal_request(request, influencer_id):
    from apps.accounts.models import InfluencerWithdrawalRequest

    inf = _influencer_for_request(request, influencer_id)
    if not inf or inf.portal_user_id != request.user.id:
        return _err('Réservé au compte influenceur.', status.HTTP_403_FORBIDDEN)

    amount = Decimal(str(request.data.get('amount', '0')))
    if amount <= 0:
        return _err('Montant invalide.')
    if inf.earnings_balance < amount:
        return _err('Solde insuffisant.')

    wr = InfluencerWithdrawalRequest.objects.create(
        influencer=inf,
        amount=amount,
        note=(request.data.get('note') or '').strip(),
    )
    log_admin_action(
        request.user, 'INFLUENCER_WITHDRAWAL_REQUEST',
        target_type='InfluencerWithdrawal', target_id=wr.id,
        detail=f'Demande {amount} FCFA',
    )
    return Response({'status': 'ok', 'id': wr.id}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def influencer_withdrawal_approve(request, withdrawal_id):
    from apps.accounts.models import InfluencerWithdrawalRequest, InfluencerWithdrawalStatus

    wr = get_object_or_404(InfluencerWithdrawalRequest, pk=withdrawal_id)
    if wr.status != InfluencerWithdrawalStatus.PENDING:
        return _err('Demande déjà traitée.')

    proof = request.FILES.get('proof_file')
    if not proof:
        return _err('Joignez une preuve de versement (fichier).')

    inf = wr.influencer
    if inf.earnings_balance < wr.amount:
        return _err('Solde influenceur insuffisant.')

    inf.earnings_balance -= wr.amount
    inf.save(update_fields=['earnings_balance'])

    wr.status = InfluencerWithdrawalStatus.APPROVED
    wr.proof_file = proof
    wr.admin_note = (request.data.get('admin_note') or '').strip()
    wr.processed_at = timezone.now()
    wr.processed_by = request.user
    wr.save()

    log_admin_action(
        request.user, 'INFLUENCER_WITHDRAWAL_APPROVE',
        target_type='InfluencerWithdrawal', target_id=wr.id,
        detail=f'Approuvé {wr.amount} FCFA',
    )
    return Response({'status': 'ok'})


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def influencer_withdrawal_reject(request, withdrawal_id):
    from apps.accounts.models import InfluencerWithdrawalRequest, InfluencerWithdrawalStatus

    wr = get_object_or_404(InfluencerWithdrawalRequest, pk=withdrawal_id)
    if wr.status != InfluencerWithdrawalStatus.PENDING:
        return _err('Demande déjà traitée.')

    wr.status = InfluencerWithdrawalStatus.REJECTED
    wr.admin_note = (request.data.get('admin_note') or '').strip()
    wr.processed_at = timezone.now()
    wr.processed_by = request.user
    wr.save()

    log_admin_action(
        request.user, 'INFLUENCER_WITHDRAWAL_REJECT',
        target_type='InfluencerWithdrawal', target_id=wr.id,
        detail=wr.admin_note or 'Rejeté',
    )
    return Response({'status': 'ok'})


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def influencer_link_portal_user(request, influencer_id):
    """Lie un compte portail à un influenceur (création credentials)."""
    from apps.accounts.models import Influencer

    inf = get_object_or_404(Influencer, pk=influencer_id)
    username = (request.data.get('username') or '').strip()
    email = (request.data.get('email') or '').strip()
    password = request.data.get('password') or ''
    if not username or not email or not password:
        return _err('username, email et password requis.')
    if User.objects.filter(username=username).exists():
        return _err('Username déjà pris.', status.HTTP_409_CONFLICT)

    portal_user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=inf.name.split(' ')[0] if inf.name else '',
        last_name=' '.join(inf.name.split(' ')[1:]) if inf.name and ' ' in inf.name else '',
        is_staff=False,
        is_superuser=False,
        is_client=False,
        is_agent=False,
    )
    inf.portal_user = portal_user
    inf.save(update_fields=['portal_user'])

    log_admin_action(
        request.user, 'INFLUENCER_PORTAL_LINK',
        target_type='Influencer', target_id=inf.id,
        detail=f'Portail @{username}',
    )
    return Response({'status': 'ok', 'portal_user_id': str(portal_user.id)})


# --- Boosts staff ---

def _serialize_boost_plan(plan) -> dict:
    return {
        'id': plan.id,
        'name': plan.name,
        'description': plan.description,
        'price': float(plan.price),
        'price_fcfa': float(plan.price_fcfa),
        'duration_hours': plan.duration_hours,
        'duration_days': plan.duration_days,
        'duration_display': plan.duration_display,
        'visibility_multiplier': float(plan.visibility_multiplier),
        'is_active': plan.is_active,
    }


@api_view(['GET', 'POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def boost_plans_list_create(request):
    from apps.boosts.models import BoostPlan

    if request.method == 'GET':
        plans = [_serialize_boost_plan(p) for p in BoostPlan.objects.order_by('price')]
        return Response({'results': plans, 'count': len(plans)})

    name = (request.data.get('name') or '').strip()
    if not name:
        return _err('name requis.')

    duration_days = request.data.get('duration_days')
    duration_hours = request.data.get('duration_hours')
    if duration_days is not None and duration_hours is None:
        duration_hours = int(duration_days) * 24
    elif duration_hours is None:
        duration_hours = 24

    price = request.data.get('price_fcfa', request.data.get('price', 0))
    plan = BoostPlan.objects.create(
        name=name,
        description=(request.data.get('description') or '').strip(),
        price=Decimal(str(price)),
        duration_hours=int(duration_hours),
        visibility_multiplier=Decimal(str(request.data.get('visibility_multiplier', '1.5'))),
        is_active=request.data.get('is_active', True) in (True, 'true', '1', 1),
    )
    log_admin_action(
        request.user, 'BOOST_PLAN_CREATE',
        target_type='BoostPlan', target_id=plan.id,
        detail=plan.name,
    )
    return Response(_serialize_boost_plan(plan), status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def boost_plan_update(request, plan_id):
    from apps.boosts.models import BoostPlan

    plan = get_object_or_404(BoostPlan, pk=plan_id)
    fields = []
    for field in ('name', 'description', 'is_active'):
        if field in request.data:
            setattr(plan, field, request.data[field])
            fields.append(field)
    if 'price' in request.data or 'price_fcfa' in request.data:
        plan.price = Decimal(str(request.data.get('price_fcfa', request.data.get('price'))))
        fields.append('price')
    if 'duration_hours' in request.data:
        plan.duration_hours = int(request.data['duration_hours'])
        fields.append('duration_hours')
    elif 'duration_days' in request.data:
        plan.duration_hours = int(request.data['duration_days']) * 24
        fields.append('duration_hours')
    if 'visibility_multiplier' in request.data:
        plan.visibility_multiplier = Decimal(str(request.data['visibility_multiplier']))
        fields.append('visibility_multiplier')
    if fields:
        plan.save(update_fields=fields + ['updated_at'])

    log_admin_action(
        request.user, 'BOOST_PLAN_UPDATE',
        target_type='BoostPlan', target_id=plan_id,
        detail=plan.name,
    )
    return Response({'status': 'ok', 'id': plan.id, 'plan': _serialize_boost_plan(plan)})


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def boost_cancel(request, boost_id):
    from apps.boosts.models import AgentBoost

    boost = get_object_or_404(AgentBoost, pk=boost_id)
    if boost.status != 'active':
        return _err('Ce boost n\'est pas actif.')

    boost.status = 'cancelled'
    boost.save(update_fields=['status', 'updated_at'])

    log_admin_action(
        request.user, 'BOOST_CANCEL',
        target_type='AgentBoost', target_id=boost_id,
        detail=f'Agent {boost.agent.username}',
    )
    return Response({'status': 'ok', 'boost_id': boost.id})


@api_view(['GET', 'POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def boost_promotions_list_create(request):
    """Liste et création des promotions boost par plan."""
    from apps.boosts.models import BoostPromotion, BoostPlan

    if request.method == 'GET':
        now = timezone.now()
        promos = BoostPromotion.objects.select_related('boost_plan').order_by('-start_date')[:50]
        results = []
        for promo in promos:
            results.append({
                'id': promo.id,
                'boost_plan_id': promo.boost_plan_id,
                'boost_plan_name': promo.boost_plan.name,
                'original_price': float(promo.boost_plan.price),
                'discount_percentage': promo.discount_percentage,
                'discounted_price': float(promo.get_discounted_price()),
                'start_date': promo.start_date.date().isoformat(),
                'end_date': promo.end_date.date().isoformat(),
                'is_active': promo.is_active,
                'is_currently_active': promo.is_currently_active,
            })
        return Response({'results': results, 'count': len(results)})

    plan_id = request.data.get('boost_plan_id')
    discount = request.data.get('discount_percentage')
    start_date = request.data.get('start_date')
    end_date = request.data.get('end_date')

    if not all([plan_id, discount, start_date, end_date]):
        return _err('Champs requis : boost_plan_id, discount_percentage, start_date, end_date.', status.HTTP_400_BAD_REQUEST)

    try:
        plan = BoostPlan.objects.get(pk=int(plan_id), is_active=True)
    except (BoostPlan.DoesNotExist, ValueError):
        return _err('Plan de boost introuvable.', status.HTTP_404_NOT_FOUND)

    try:
        discount_int = int(discount)
        if not (1 <= discount_int <= 99):
            raise ValueError
    except ValueError:
        return _err('discount_percentage doit être entre 1 et 99.', status.HTTP_400_BAD_REQUEST)

    from django.utils.dateparse import parse_date
    from datetime import datetime, time
    from django.utils.timezone import make_aware

    start = parse_date(str(start_date))
    end = parse_date(str(end_date))
    if not start or not end:
        return _err('Dates invalides (format attendu: YYYY-MM-DD).', status.HTTP_400_BAD_REQUEST)
    if end <= start:
        return _err('La date de fin doit être après la date de début.', status.HTTP_400_BAD_REQUEST)

    existing = BoostPromotion.objects.filter(
        boost_plan=plan,
        is_active=True,
        end_date__gte=timezone.now(),
    ).first()
    if existing:
        return _err(
            f'Le plan "{plan.name}" a déjà une promo active (valide jusqu\'au {existing.end_date.date()}). '
            f'Supprimez-la ou attendez son expiration avant d\'en créer une nouvelle.',
            status.HTTP_409_CONFLICT,
        )

    promo = BoostPromotion.objects.create(
        boost_plan=plan,
        discount_percentage=discount_int,
        start_date=make_aware(datetime.combine(start, time.min)),
        end_date=make_aware(datetime.combine(end, time.max)),
        is_active=True,
    )

    log_admin_action(
        request.user, 'BOOST_PROMO_CREATE',
        target_type='BoostPromotion', target_id=promo.id,
        detail=f'{plan.name} -{discount_int}% du {start} au {end}',
    )
    return Response({
        'status': 'ok',
        'id': promo.id,
        'boost_plan_name': plan.name,
        'discount_percentage': discount_int,
        'discounted_price': float(promo.get_discounted_price()),
        'start_date': start.isoformat(),
        'end_date': end.isoformat(),
    }, status=status.HTTP_201_CREATED)


@api_view(['PATCH', 'DELETE'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def boost_promotion_update(request, promo_id):
    """Activer/désactiver ou supprimer une promotion boost."""
    from apps.boosts.models import BoostPromotion

    promo = get_object_or_404(BoostPromotion, pk=promo_id)

    if request.method == 'DELETE':
        promo.delete()
        log_admin_action(
            request.user, 'BOOST_PROMO_DELETE',
            target_type='BoostPromotion', target_id=promo_id,
        )
        return Response({'status': 'ok'})

    is_active = request.data.get('is_active')
    if is_active is not None:
        promo.is_active = bool(is_active)
        promo.save(update_fields=['is_active', 'updated_at'])

    return Response({'status': 'ok', 'id': promo.id, 'is_active': promo.is_active})


@api_view(['GET', 'POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def concierge_notes(request):
    """Notes internes conciergerie — mémos équipe support."""
    from apps.core.models import StaffConciergeNote

    if request.method == 'GET':
        limit = min(int(request.query_params.get('limit', 20)), 100)
        notes = StaffConciergeNote.objects.select_related('author').order_by('-updated_at')[:limit]
        latest = notes[0] if notes else None
        return Response({
            'latest': {
                'id': latest.id,
                'content': latest.content,
                'author': latest.author.username if latest and latest.author_id else None,
                'updated_at': latest.updated_at.isoformat() if latest else None,
            } if latest else None,
            'results': [
                {
                    'id': n.id,
                    'content': n.content,
                    'author': n.author.username if n.author_id else 'system',
                    'updated_at': n.updated_at.isoformat(),
                }
                for n in notes
            ],
        })

    content = (request.data.get('content') or '').strip()
    if not content:
        return _err('content requis.')

    notification_id = request.data.get('admin_notification_id')
    notification = None
    if notification_id:
        notification = get_object_or_404(AdminNotification, pk=notification_id)

    note = StaffConciergeNote.objects.create(
        author=request.user,
        content=content,
        admin_notification=notification,
    )
    log_admin_action(
        request.user, 'CONCIERGE_NOTE_SAVE',
        target_type='StaffConciergeNote', target_id=note.id,
        detail=content[:80],
    )
    return Response({
        'id': note.id,
        'content': note.content,
        'updated_at': note.updated_at.isoformat(),
    }, status=status.HTTP_201_CREATED)


def _wallet_period_filter(period: str):
    """Retourne la date de début pour filtrer selon la période demandée."""
    from datetime import timedelta
    now = timezone.now()
    if period == 'today':
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == 'week':
        return now - timedelta(days=7)
    if period == 'month':
        return now - timedelta(days=30)
    if period == 'year':
        return now - timedelta(days=365)
    return None  # 'all'


def _build_wallet_history(period: str):
    """Construit la liste des entrées de trésorerie filtrées par période."""
    from apps.wallets.models import Transaction, PayoutRequest
    from apps.core.choices import PayoutRequestStatus

    since = _wallet_period_filter(period)
    history = []

    tx_qs = Transaction.objects.filter(
        transaction_type__in=['BOOST_PAYMENT', 'MISSION_PAYMENT', 'PAYOUT', 'COMMISSION'],
    ).select_related('wallet__user').only(
        'id', 'transaction_type', 'amount', 'description', 'created_at',
        'wallet__user__referral_code', 'wallet__user__username',
        'wallet__user__first_name', 'wallet__user__last_name',
    )
    if since:
        tx_qs = tx_qs.filter(created_at__gte=since)
    for t in tx_qs.order_by('-created_at')[:60]:
        u = t.wallet.user if t.wallet else None
        history.append({
            'id': str(t.id),
            'type': t.transaction_type,
            'amount': float(t.amount),
            'user_code': (u.referral_code or u.username or str(u.id)) if u else '—',
            'user_name': (u.get_full_name() or u.username) if u else '—',
            'description': t.description[:100] if t.description else '',
            'created_at': t.created_at.strftime('%d/%m/%Y %H:%M'),
            'created_at_iso': t.created_at.isoformat(),
        })

    try:
        pr_qs = PayoutRequest.objects.filter(
            status=PayoutRequestStatus.APPROVED,
        ).select_related('wallet__user').only(
            'id', 'amount', 'phone_number', 'created_at',
            'wallet__user__referral_code', 'wallet__user__username',
            'wallet__user__first_name', 'wallet__user__last_name',
        )
        if since:
            pr_qs = pr_qs.filter(created_at__gte=since)
        for pr in pr_qs.order_by('-created_at')[:30]:
            u = pr.wallet.user if pr.wallet else None
            history.append({
                'id': str(pr.id),
                'type': 'RETRAIT_APPROUVÉ',
                'amount': float(pr.amount),
                'user_code': (u.referral_code or u.username or str(u.id)) if u else (pr.phone_number or '—'),
                'user_name': (u.get_full_name() or u.username) if u else '—',
                'description': f'Retrait · {pr.phone_number or "—"}',
                'created_at': pr.created_at.strftime('%d/%m/%Y %H:%M'),
                'created_at_iso': pr.created_at.isoformat(),
            })
    except Exception:
        pass

    history.sort(key=lambda x: x['created_at_iso'], reverse=True)
    return history[:80]


def _wallet_summary_compute(period: str) -> dict:
    """Calcul brut du wallet summary (sans cache)."""
    from apps.boosts.models import AgentBoost
    from apps.escrow.models import Escrow, EscrowSplitRecord

    since = _wallet_period_filter(period)

    split_qs = EscrowSplitRecord.objects.filter(
        beneficiary_type=EscrowSplitRecord.BeneficiaryType.PLATFORM,
    )
    boost_qs = AgentBoost.objects.all()
    if since:
        split_qs = split_qs.filter(created_at__gte=since)
        boost_qs = boost_qs.filter(created_at__gte=since)

    platform_revenue = split_qs.aggregate(total=Sum('amount_fcfa'))['total'] or Decimal('0')
    boost_revenue = boost_qs.aggregate(total=Sum('purchase_amount'))['total'] or Decimal('0')

    escrow_held = Escrow.objects.filter(
        status__in=['HELD', 'DISPUTED'],
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    influencer_commissions = Decimal('0')
    try:
        inf_qs = EscrowSplitRecord.objects.filter(beneficiary_type='INFLUENCER')
        if since:
            inf_qs = inf_qs.filter(created_at__gte=since)
        influencer_commissions = inf_qs.aggregate(t=Sum('amount_fcfa'))['t'] or Decimal('0')
    except Exception:
        pass

    return {
        'platform_revenue': float(platform_revenue),
        'boost_revenue': float(boost_revenue),
        'total_platform': float(platform_revenue + boost_revenue),
        'escrow_held': float(escrow_held),
        'influencer_commissions': float(influencer_commissions),
    }


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def platform_wallet_summary(request):
    """Trésorerie plateforme : revenus, boosts, commissions, historique."""
    from django.core.cache import cache

    period = request.query_params.get('period', 'all')
    cache_key = f'wallet_summary_{period}'

    cached = cache.get(cache_key)
    if cached:
        return Response(cached)

    kpis = _wallet_summary_compute(period)
    history = _build_wallet_history(period)

    payload = {**kpis, 'history': history, 'period': period}
    cache.set(cache_key, payload, timeout=30)  # 30 s — transparence temps réel

    return Response(payload)


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def wallet_export(request):
    """Export CSV ou PDF de l'historique trésorerie."""
    import csv as csv_mod
    from django.http import HttpResponse

    fmt = request.query_params.get('format', 'csv')
    period = request.query_params.get('period', 'all')
    history = _build_wallet_history(period)

    period_label = {'today': "Aujourd'hui", 'week': 'Semaine', 'month': 'Mois', 'year': 'Année'}.get(period, 'Tout')

    if fmt == 'pdf':
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        import io

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                                topMargin=1.5 * cm, bottomMargin=1.5 * cm)
        styles = getSampleStyleSheet()
        elems = []
        elems.append(Paragraph(f'Trésorerie FONAQO — {period_label}', styles['Title']))
        elems.append(Paragraph(f'Exporté le {timezone.now().strftime("%d/%m/%Y %H:%M")}', styles['Normal']))
        elems.append(Spacer(1, 0.5 * cm))

        headers = ['Date', 'Type', 'Code utilisateur', 'Nom', 'Montant (FCFA)', 'Description']
        rows = [headers]
        for h in history:
            rows.append([
                h['created_at'],
                h['type'],
                h['user_code'],
                h['user_name'],
                f"{h['amount']:,.0f}",
                h['description'][:60],
            ])

        col_widths = [3.5 * cm, 4 * cm, 3.5 * cm, 4 * cm, 3.5 * cm, 8 * cm]
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFD100')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9F9F9')]),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#DDDDDD')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elems.append(t)
        doc.build(elems)

        buf.seek(0)
        resp = HttpResponse(buf, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="tresorerie_fonaqo_{period}.pdf"'
        return resp

    # CSV (défaut — ouvrable dans Excel)
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="tresorerie_fonaqo_{period}.csv"'
    writer = csv_mod.writer(response)
    writer.writerow(['Date', 'Type', 'Code utilisateur', 'Nom', 'Montant (FCFA)', 'Description'])
    for h in history:
        writer.writerow([h['created_at'], h['type'], h['user_code'], h['user_name'], h['amount'], h['description']])
    return response


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def artisan_create(request):
    """Créer une fiche artisan dans l'annuaire LeBonCoin."""
    from apps.leboncoin.models import LocalListing

    name = (request.data.get('name') or '').strip()
    phone = (request.data.get('phone_number') or request.data.get('phone') or '').strip()
    if not name:
        return _err('Le nom est requis.')

    listing = LocalListing.objects.create(
        name=name,
        category=LocalListing.Category.ARTISAN,
        specialty=(request.data.get('specialties') or request.data.get('specialty') or '')[:120],
        description=(request.data.get('description') or '')[:2000],
        city=(request.data.get('city') or 'Cotonou')[:100],
        district=(request.data.get('district') or request.data.get('address') or '')[:100],
        phone=phone,
        email=(request.data.get('email') or '')[:254],
        is_active=True,
        is_featured=bool(request.data.get('is_featured')),
    )

    log_admin_action(
        request.user, 'ARTISAN_CREATE',
        target_type='LocalListing', target_id=str(listing.id),
        detail=f'Artisan {listing.name}',
    )
    return Response({
        'status': 'ok',
        'listing_id': str(listing.id),
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def artisan_revoke(request, listing_id):
    from apps.leboncoin.models import LocalListing

    listing = get_object_or_404(
        LocalListing,
        pk=listing_id,
        category=LocalListing.Category.ARTISAN,
    )
    listing.is_active = False
    listing.save(update_fields=['is_active', 'updated_at'])
    log_admin_action(
        request.user, 'ARTISAN_REVOKE',
        target_type='LocalListing', target_id=str(listing_id),
        detail=listing.name,
    )
    return Response({'status': 'ok'})


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def agent_toggle_internal(request, profile_id):
    from apps.accounts.models import AgentProfile

    profile = get_object_or_404(
        AgentProfile.objects.select_related('user'),
        pk=profile_id,
        user__is_agent=True,
    )
    profile.is_internal = not profile.is_internal
    profile.save(update_fields=['is_internal', 'updated_at'])
    log_admin_action(
        request.user, 'AGENT_TOGGLE_INTERNAL',
        target_type='AgentProfile', target_id=profile_id,
        detail=f'@{profile.user.username} internal={profile.is_internal}',
    )
    return Response({
        'status': 'ok',
        'profile_id': profile.id,
        'is_internal': profile.is_internal,
    })


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def badge_queue(request):
    from apps.accounts.models import AgentProfile
    from apps.core.choices import AgentBadgeStatus

    base_qs = AgentProfile.objects.filter(
        badge_status=AgentBadgeStatus.PENDING,
    ).select_related('user').order_by('-badge_requested_at')
    rows = list(base_qs[:100])
    return Response({
        'count': base_qs.count(),
        'results': [
            {
                'id': p.id,
                'user_id': str(p.user_id),
                'username': p.user.username,
                'full_name': p.user.get_full_name(),
                'agent_code': p.agent_code,
                'badge_photo': p.badge_photo.url if p.badge_photo else None,
                'requested_at': (
                    p.badge_requested_at.strftime('%Y-%m-%d %H:%M')
                    if p.badge_requested_at else None
                ),
            }
            for p in rows
        ],
    })


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def badge_approve(request, profile_id):
    from apps.accounts.agent_codes import ensure_agent_code
    from apps.accounts.models import AgentProfile
    from apps.core.choices import AgentBadgeStatus
    from apps.core.email_service import send_badge_approved_email

    profile = get_object_or_404(
        AgentProfile.objects.select_related('user'),
        pk=profile_id,
    )
    if profile.badge_status != AgentBadgeStatus.PENDING:
        return _err('Demande badge non en attente.')

    ensure_agent_code(profile)
    profile.badge_status = AgentBadgeStatus.APPROVED
    profile.badge_approved_at = timezone.now()
    profile.badge_rejection_reason = ''
    profile.save(update_fields=[
        'badge_status', 'badge_approved_at', 'badge_rejection_reason', 'updated_at',
    ])
    send_badge_approved_email(profile.user, profile.agent_code)
    log_admin_action(
        request.user, 'BADGE_APPROVE',
        target_type='AgentProfile', target_id=profile_id,
        detail=f'@{profile.user.username}',
    )
    return Response({'status': 'ok', 'agent_code': profile.agent_code})


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def badge_download(request, profile_id):
    """Génère et télécharge le PDF badge professionnel (admin)."""
    from django.http import HttpResponse

    from apps.accounts.agent_codes import ensure_agent_code
    from apps.accounts.models import AgentProfile
    from apps.accounts.pro_badge import build_agent_pro_badge_pdf
    from apps.core.choices import AgentBadgeStatus
    from apps.core.email_service import send_badge_approved_email

    profile = get_object_or_404(
        AgentProfile.objects.select_related('user'),
        pk=profile_id,
        user__is_agent=True,
    )
    if not profile.badge_photo and not profile.selfie_photo:
        return _err(
            'Aucune photo badge ou selfie KYC — impossible de générer le badge.',
            status.HTTP_400_BAD_REQUEST,
        )

    was_pending = profile.badge_status != AgentBadgeStatus.APPROVED
    if was_pending:
        ensure_agent_code(profile)
        profile.badge_status = AgentBadgeStatus.APPROVED
        profile.badge_approved_at = timezone.now()
        profile.badge_rejection_reason = ''
        profile.save(update_fields=[
            'badge_status', 'badge_approved_at', 'badge_rejection_reason', 'updated_at',
        ])
        send_badge_approved_email(profile.user, profile.agent_code)
        log_admin_action(
            request.user, 'BADGE_GENERATE',
            target_type='AgentProfile', target_id=profile_id,
            detail=f'@{profile.user.username}',
        )
    else:
        ensure_agent_code(profile)

    pdf_bytes = build_agent_pro_badge_pdf(profile.user, profile)
    code = profile.agent_code or profile.user.username
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="badge-{code}.pdf"'
    return response


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def badge_reject(request, profile_id):
    from apps.accounts.models import AgentProfile
    from apps.core.choices import AgentBadgeStatus

    reason = (request.data.get('reason') or '').strip()
    profile = get_object_or_404(AgentProfile.objects.select_related('user'), pk=profile_id)
    if profile.badge_status != AgentBadgeStatus.PENDING:
        return _err('Demande badge non en attente.')

    profile.badge_status = AgentBadgeStatus.REJECTED
    profile.badge_rejection_reason = reason
    profile.save(update_fields=['badge_status', 'badge_rejection_reason', 'updated_at'])
    log_admin_action(
        request.user, 'BADGE_REJECT',
        target_type='AgentProfile', target_id=profile_id,
        detail=reason or f'@{profile.user.username}',
    )
    return Response({'status': 'ok'})


@api_view(['GET', 'POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def staff_users(request):
    if not request.user.is_superuser:
        return _err('Réservé au Super Admin.', status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        rows = []
        for u in User.objects.filter(Q(is_staff=True) | Q(is_superuser=True)).order_by('-date_joined'):
            rows.append({
                'id': str(u.id),
                'username': u.username,
                'email': u.email,
                'full_name': u.get_full_name(),
                'is_superuser': u.is_superuser,
                'is_staff': u.is_staff,
                'is_active': u.is_active,
                'date_joined': u.date_joined.strftime('%Y-%m-%d'),
            })
        return Response({'results': rows})

    username = (request.data.get('username') or '').strip()
    email = (request.data.get('email') or '').strip()
    password = request.data.get('password') or ''
    role = (request.data.get('role') or 'manager').strip().lower()
    if not username or not email or not password:
        return _err('username, email et password requis.')

    if User.objects.filter(username=username).exists():
        return _err('Username déjà pris.', status.HTTP_409_CONFLICT)

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=request.data.get('first_name', ''),
        last_name=request.data.get('last_name', ''),
        is_staff=True,
        is_superuser=(role == 'superadmin'),
        is_client=False,
        is_agent=False,
    )
    log_admin_action(
        request.user, 'STAFF_CREATE',
        target_type='User', target_id=user.id,
        detail=f'Staff @{user.username} role={role}',
    )
    return Response({'status': 'ok', 'id': str(user.id)}, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def staff_user_delete(request, user_id):
    """Supprimer un compte staff (gestionnaire uniquement — pas les Super Admin)."""
    if not request.user.is_superuser:
        return _err('Réservé au Super Admin.', status.HTTP_403_FORBIDDEN)

    target = get_object_or_404(User, pk=user_id)
    if not (target.is_staff or target.is_superuser):
        return _err('Cet utilisateur n\'est pas un compte staff.', status.HTTP_400_BAD_REQUEST)
    if target.is_superuser:
        return _err('Impossible de supprimer un Super Admin.', status.HTTP_403_FORBIDDEN)
    if target.id == request.user.id:
        return _err('Vous ne pouvez pas supprimer votre propre compte.', status.HTTP_400_BAD_REQUEST)

    username = target.username
    target.delete()
    log_admin_action(
        request.user, 'STAFF_DELETE',
        target_type='User',
        detail=f'Compte staff @{username} supprimé',
    )
    return Response({'status': 'ok', 'deleted': username})


@api_view(['GET', 'PATCH'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsBackofficeUser])
def staff_me(request):
    """Profil du compte staff connecté (session back-office)."""
    user = request.user

    if request.method == 'GET':
        from apps.accounts.models import Influencer
        return Response({
            'id': str(user.id),
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
            'role_label': (
                'Super Admin' if user.is_superuser
                else 'Influenceur' if Influencer.objects.filter(portal_user=user).exists()
                else 'Gestionnaire' if user.is_staff
                else 'Staff'
            ),
            'date_joined': user.date_joined.strftime('%Y-%m-%d'),
        })

    fields = []
    for field in ('first_name', 'last_name', 'email'):
        if field in request.data:
            val = (request.data.get(field) or '').strip()
            if field == 'email' and val:
                if User.objects.filter(email__iexact=val).exclude(pk=user.pk).exists():
                    return _err('Cet e-mail est déjà utilisé.', status.HTTP_409_CONFLICT)
            setattr(user, field, val)
            fields.append(field)

    if not fields:
        return _err('Aucun champ à mettre à jour (first_name, last_name, email).')

    user.save(update_fields=fields)
    log_admin_action(
        request.user, 'STAFF_PROFILE_UPDATE',
        target_type='User', target_id=user.id,
        detail=', '.join(fields),
    )
    return Response({'status': 'ok', 'updated': fields})


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsBackofficeUser])
def staff_change_password(request):
    """Changement de mot de passe staff — conserve la session active."""
    old_password = request.data.get('old_password') or ''
    new_password = request.data.get('new_password') or ''
    confirm_password = request.data.get('confirm_password') or ''

    if not old_password or not new_password or not confirm_password:
        return _err('Ancien, nouveau et confirmation requis.')
    if new_password != confirm_password:
        return _err('Les nouveaux mots de passe ne correspondent pas.')
    if len(str(new_password)) < 8:
        return _err('Le mot de passe doit contenir au moins 8 caractères.')
    if not request.user.check_password(old_password):
        return _err('Ancien mot de passe incorrect.', status.HTTP_403_FORBIDDEN)

    user = request.user
    user.set_password(new_password)
    user.save(update_fields=['password'])
    update_session_auth_hash(request, user)

    log_admin_action(
        user, 'STAFF_PASSWORD_CHANGE',
        target_type='User', target_id=user.id,
        detail='Mot de passe modifié',
    )
    return Response({'status': 'ok', 'message': 'Mot de passe mis à jour'})


# --- Modération utilisateurs ---

@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def user_suspend(request, user_id):
    """Suspendre un compte client ou agent."""
    user = get_object_or_404(User, pk=user_id)
    reason = (request.data.get('reason') or '').strip()
    if not user.is_active:
        return _err('Compte déjà suspendu.')
    user.is_active = False
    user.save(update_fields=['is_active'])
    from apps.core.email_service import send_account_suspended_email
    send_account_suspended_email(user, reason)
    log_admin_action(
        request.user, 'USER_SUSPEND',
        target_type='User', target_id=user.id,
        detail=reason or f'@{user.username}',
    )
    return Response({'status': 'ok', 'is_active': False})


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def user_reactivate(request, user_id):
    """Réactiver un compte suspendu."""
    user = get_object_or_404(User, pk=user_id)
    if user.is_active:
        return _err('Compte déjà actif.')
    user.is_active = True
    user.save(update_fields=['is_active'])
    from apps.core.email_service import send_account_reactivated_email
    send_account_reactivated_email(user)
    log_admin_action(
        request.user, 'USER_REACTIVATE',
        target_type='User', target_id=user.id,
        detail=f'@{user.username}',
    )
    return Response({'status': 'ok', 'is_active': True})


# --- Demandes réinitialisation mot de passe ---

@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def password_reset_queue(request):
    from apps.core.models import PasswordResetRequest

    base_qs = PasswordResetRequest.objects.filter(
        status=PasswordResetRequest.Status.PENDING,
    ).select_related('user').order_by('-requested_at')
    pending = list(base_qs[:100])
    return Response({
        'count': base_qs.count(),
        'results': [
            {
                'id': r.id,
                'phone_number': r.phone_number,
                'username': r.user.username,
                'full_name': r.user.get_full_name(),
                'requested_at': r.requested_at.strftime('%Y-%m-%d %H:%M'),
            }
            for r in pending
        ],
    })


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def password_reset_process(request, request_id):
    import secrets
    import string

    from apps.core.models import PasswordResetRequest

    wr = get_object_or_404(PasswordResetRequest, pk=request_id)
    if wr.status != PasswordResetRequest.Status.PENDING:
        return _err('Demande déjà traitée.')

    alphabet = string.ascii_letters + string.digits
    temp_password = ''.join(secrets.choice(alphabet) for _ in range(10))
    user = wr.user
    user.set_password(temp_password)
    user.save(update_fields=['password'])

    wr.status = PasswordResetRequest.Status.COMPLETED
    wr.temp_password = temp_password
    wr.processed_by = request.user
    wr.processed_at = timezone.now()
    wr.save()

    phone = wr.phone_number
    sms_message = (
        f'FONACO — Votre mot de passe temporaire est : {temp_password}. '
        f'Connectez-vous et changez-le immédiatement dans Paramètres > Sécurité.'
    )

    log_admin_action(
        request.user, 'PASSWORD_RESET_MANUAL',
        target_type='PasswordResetRequest', target_id=wr.id,
        detail=f'@{user.username}',
    )
    return Response({
        'status': 'ok',
        'phone_number': phone,
        'temp_password': temp_password,
        'sms_message': sms_message,
    })


# ─── TEAM MANAGERS ────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def managers_list_create(request):
    """Liste des managers de brigade / Créer un nouveau manager."""
    from apps.accounts.models import TeamManager, AgentProfile
    from apps.missions.models import Mission

    if request.method == 'GET':
        qs = TeamManager.objects.annotate(
            agents_total=Count('agents', distinct=True),
            completed_missions=Count(
                'agents__user__missions_assigned',
                filter=Q(agents__user__missions_assigned__status='COMPLETED'),
                distinct=True,
            ),
        ).order_by('-created_at')

        data = []
        for m in qs:
            data.append({
                'id': m.id,
                'name': m.name,
                'commission_rate': float(m.commission_rate),
                'max_agents': m.max_agents,
                'agent_count': m.agents_total,
                'completed_missions': m.completed_missions,
                'earnings_balance': float(m.earnings_balance),
                'bio': m.bio,
                'created_at': m.created_at.strftime('%d/%m/%Y'),
            })
        return Response({'results': data, 'count': len(data)})

    # POST — créer
    if not request.user.is_superuser:
        return _err('Réservé au Super Admin.', status.HTTP_403_FORBIDDEN)
    name = (request.data.get('name') or '').strip()
    if not name:
        return _err('Le nom est obligatoire.', status.HTTP_400_BAD_REQUEST)
    rate = request.data.get('commission_rate', '0.02')
    max_agents = request.data.get('max_agents', 10)
    bio = (request.data.get('bio') or '').strip()
    try:
        rate = Decimal(str(rate))
        if not (Decimal('0') <= rate <= Decimal('0.5')):
            raise ValueError
    except Exception:
        return _err('Taux invalide (0.00 – 0.50).', status.HTTP_400_BAD_REQUEST)

    mgr = TeamManager.objects.create(
        name=name, commission_rate=rate, max_agents=int(max_agents), bio=bio,
    )
    log_admin_action(request.user, 'MANAGER_CREATE', target_type='TeamManager', target_id=mgr.id,
                     detail=f'Manager {name}')
    return Response({'id': mgr.id, 'name': mgr.name}, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH', 'DELETE'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def manager_detail(request, manager_id):
    """Détail d'un manager, mise à jour, ou suppression."""
    from apps.accounts.models import TeamManager, AgentProfile
    from apps.missions.models import Mission

    mgr = get_object_or_404(TeamManager, pk=manager_id)

    if request.method == 'GET':
        agents = AgentProfile.objects.filter(manager=mgr).select_related('user').annotate(
            completed=Count(
                'user__missions_assigned',
                filter=Q(user__missions_assigned__status='COMPLETED'),
            ),
            disputed=Count(
                'user__missions_assigned',
                filter=Q(user__missions_assigned__status='DISPUTED'),
            ),
        )
        agents_data = [{
            'id': str(ap.user.id),
            'username': ap.user.username or '',
            'name': ap.user.get_full_name() or ap.user.username or '',
            'agent_code': ap.agent_code or '',
            'kyc_status': ap.kyc_status,
            'average_rating': float(ap.average_rating),
            'completed_missions': ap.completed,
            'disputed_missions': ap.disputed,
        } for ap in agents]

        return Response({
            'id': mgr.id,
            'name': mgr.name,
            'commission_rate': float(mgr.commission_rate),
            'max_agents': mgr.max_agents,
            'earnings_balance': float(mgr.earnings_balance),
            'bio': mgr.bio,
            'agent_count': len(agents_data),
            'agents': agents_data,
            'created_at': mgr.created_at.strftime('%d/%m/%Y'),
        })

    if request.method == 'PATCH':
        if not request.user.is_superuser:
            return _err('Réservé au Super Admin.', status.HTTP_403_FORBIDDEN)
        for field in ('name', 'bio', 'max_agents'):
            val = request.data.get(field)
            if val is not None:
                setattr(mgr, field, val)
        if 'commission_rate' in request.data:
            try:
                mgr.commission_rate = Decimal(str(request.data['commission_rate']))
            except Exception:
                return _err('Taux invalide.', status.HTTP_400_BAD_REQUEST)
        mgr.save()
        log_admin_action(request.user, 'MANAGER_UPDATE', target_type='TeamManager', target_id=mgr.id,
                         detail=f'Manager {mgr.name}')
        return Response({'status': 'ok'})

    # DELETE
    if not request.user.is_superuser:
        return _err('Réservé au Super Admin.', status.HTTP_403_FORBIDDEN)
    name = mgr.name
    mgr.delete()
    log_admin_action(request.user, 'MANAGER_DELETE', target_type='TeamManager',
                     detail=f'Manager {name} supprimé')
    return Response({'status': 'ok'})


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def agents_free(request):
    """Liste des agents sans manager (libres), filtrables par nom/username."""
    from apps.accounts.models import AgentProfile
    q = (request.query_params.get('q') or '').strip()
    qs = AgentProfile.objects.filter(manager__isnull=True).select_related('user')
    if q:
        qs = qs.filter(
            Q(user__username__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(agent_code__icontains=q)
        )
    data = [{
        'id': str(ap.user.id),
        'profile_id': ap.id,
        'username': ap.user.username or '',
        'name': ap.user.get_full_name() or ap.user.username or '',
        'agent_code': ap.agent_code or '',
        'kyc_status': ap.kyc_status,
        'average_rating': float(ap.average_rating),
    } for ap in qs[:30]]
    return Response({'results': data})


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def manager_assign_agent(request, manager_id):
    """Assigner un agent libre à une brigade."""
    from apps.accounts.models import TeamManager, AgentProfile
    if not request.user.is_superuser:
        return _err('Réservé au Super Admin.', status.HTTP_403_FORBIDDEN)
    mgr = get_object_or_404(TeamManager, pk=manager_id)
    profile_id = request.data.get('profile_id')
    if not profile_id:
        return _err('profile_id obligatoire.', status.HTTP_400_BAD_REQUEST)
    ap = get_object_or_404(AgentProfile, pk=profile_id)
    if ap.manager_id is not None:
        return _err('Cet agent est déjà dans une brigade.', status.HTTP_409_CONFLICT)
    if mgr.agent_count >= mgr.max_agents:
        return _err(f'Brigade pleine ({mgr.max_agents} agents max).', status.HTTP_409_CONFLICT)
    ap.manager = mgr
    ap.save(update_fields=['manager', 'updated_at'])
    log_admin_action(request.user, 'MANAGER_ASSIGN', target_type='AgentProfile', target_id=ap.id,
                     detail=f'@{ap.user.username} → Brigade {mgr.name}')
    return Response({'status': 'ok', 'agent': ap.user.username, 'manager': mgr.name})


@api_view(['POST'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def manager_unassign_agent(request, manager_id):
    """Retirer un agent d'une brigade (le rendre libre)."""
    from apps.accounts.models import AgentProfile
    if not request.user.is_superuser:
        return _err('Réservé au Super Admin.', status.HTTP_403_FORBIDDEN)
    profile_id = request.data.get('profile_id')
    ap = get_object_or_404(AgentProfile, pk=profile_id, manager_id=manager_id)
    ap.manager = None
    ap.save(update_fields=['manager', 'updated_at'])
    log_admin_action(request.user, 'MANAGER_UNASSIGN', target_type='AgentProfile', target_id=ap.id,
                     detail=f'@{ap.user.username} retiré de la brigade #{manager_id}')
    return Response({'status': 'ok'})

