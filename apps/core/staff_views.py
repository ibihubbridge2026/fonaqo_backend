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


_ACTIVE_MISSION_STATUSES = [
    MissionStatus.PENDING,
    MissionStatus.ACCEPTED,
    MissionStatus.ON_THE_WAY,
    MissionStatus.ARRIVED,
    MissionStatus.IN_PROGRESS,
    MissionStatus.IN_PROGRESS_REVIEW,
    MissionStatus.DISPUTED,
]


def _err(message: str, code=status.HTTP_400_BAD_REQUEST):
    return Response({'message': message}, status=code)


def _revenue_split_percentages():
    """Répartition agent / plateforme / influenceur — config plateforme ou splits escrow."""
    from apps.escrow.models import EscrowSplitRecord

    agent_cfg = float(PlatformConfigService.get_decimal(SPLIT_AGENT_PCT_KEY, '88'))
    platform_cfg = float(PlatformConfigService.get_decimal(SPLIT_PLATFORM_PCT_KEY, '10'))
    influencer_cfg = float(PlatformConfigService.get_decimal(SPLIT_INFLUENCER_PCT_KEY, '2'))

    bt = EscrowSplitRecord.BeneficiaryType
    totals = {
        bt.AGENT: EscrowSplitRecord.objects.filter(beneficiary_type=bt.AGENT).aggregate(
            t=Sum('amount_fcfa'),
        )['t'] or Decimal('0'),
        bt.PLATFORM: EscrowSplitRecord.objects.filter(beneficiary_type=bt.PLATFORM).aggregate(
            t=Sum('amount_fcfa'),
        )['t'] or Decimal('0'),
        bt.INFLUENCER: EscrowSplitRecord.objects.filter(beneficiary_type=bt.INFLUENCER).aggregate(
            t=Sum('amount_fcfa'),
        )['t'] or Decimal('0'),
    }
    grand = sum(totals.values())
    if grand <= 0:
        return {
            'agent_pct': agent_cfg,
            'platform_pct': platform_cfg,
            'influencer_pct': influencer_cfg,
            'configured': True,
        }
    return {
        'agent_pct': round(float(totals[bt.AGENT] / grand * 100), 1),
        'platform_pct': round(float(totals[bt.PLATFORM] / grand * 100), 1),
        'influencer_pct': round(float(totals[bt.INFLUENCER] / grand * 100), 1),
        'configured': False,
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

    limit = min(int(request.query_params.get('limit', 12)), 30)
    items = []

    for notif in AdminNotification.objects.order_by('-created_at')[:limit]:
        items.append({
            'timestamp': notif.created_at.isoformat(),
            'time': notif.created_at.strftime('%H:%M'),
            'type': 'notification',
            'label': notif.title,
            'detail': (notif.message or '')[:140],
            'severity': notif.severity,
        })

    for entry in AdminAuditLog.objects.select_related('admin').order_by('-created_at')[:limit]:
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
    )[:limit]:
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
    return Response({'results': items[:limit], 'count': min(len(items), limit)})


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
                'duration_hours': p.duration_hours,
                'visibility_multiplier': float(p.visibility_multiplier),
                'is_active': p.is_active,
            })
        split = _revenue_split_percentages()
        return Response({
            'FEES_URGENT': str(PlatformConfigService.get_decimal(FEES_URGENT_KEY, '500')),
            'FEES_CONFIDENTIAL': str(
                PlatformConfigService.get_decimal(FEES_CONFIDENTIAL_KEY, '500'),
            ),
            'fees_urgent': int(PlatformConfigService.get_decimal(FEES_URGENT_KEY, '500')),
            'fees_confidential': int(
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
    for key, val in payload.items():
        if key not in config_map:
            continue
        cfg_key, desc = config_map[key]
        PlatformConfigService.set_value(cfg_key, val, desc)
        updated[cfg_key] = str(val)

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
    ).select_related('wallet__user').order_by('-created_at')[:100]

    results = []
    for payout in qs:
        user = payout.wallet.user
        results.append({
            'id': str(payout.id),
            'amount': float(payout.amount),
            'status': payout.status,
            'username': user.username,
            'agent_name': user.get_full_name() or user.username,
            'user_id': str(user.id),
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
        'mission__client', 'mission__agent', 'mission__escrow',
    ).order_by('-created_at')[:100]

    results = []
    for d in qs:
        m = d.mission
        escrow = getattr(m, 'escrow', None)
        results.append({
            'dispute_id': d.id,
            'mission_id': str(m.id),
            'mission_ref': str(m.id)[:8].upper(),
            'client': m.client.username or m.client.phone_number,
            'agent': m.agent.username if m.agent_id else None,
            'amount': float(escrow.amount) if escrow else float(m.price or 0),
            'escrow_status': escrow.status if escrow else '—',
            'status': d.status,
            'title': d.title,
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
    if 'price' in request.data:
        plan.price = Decimal(str(request.data['price']))
        fields.append('price')
    if 'duration_hours' in request.data:
        plan.duration_hours = int(request.data['duration_hours'])
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
    return Response({'status': 'ok', 'id': plan.id})


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


@api_view(['GET'])
@authentication_classes(_STAFF_AUTH)
@permission_classes([IsAdminUser])
def platform_wallet_summary(request):
    """Trésorerie plateforme : revenus, boosts, commissions, historique."""
    from apps.boosts.models import AgentBoost
    from apps.escrow.models import Escrow, EscrowSplitRecord
    from apps.wallets.models import Transaction

    platform_revenue = EscrowSplitRecord.objects.filter(
        beneficiary_type=EscrowSplitRecord.BeneficiaryType.PLATFORM,
    ).aggregate(total=Sum('amount_fcfa'))['total'] or Decimal('0')

    boost_revenue = AgentBoost.objects.aggregate(
        total=Sum('purchase_amount'),
    )['total'] or Decimal('0')

    escrow_held = Escrow.objects.filter(
        status__in=['HELD', 'DISPUTED'],
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    influencer_pending = Decimal('0')
    try:
        from apps.accounts.models import Influencer
        influencer_pending = Influencer.objects.aggregate(
            t=Sum('earnings_balance'),
        )['t'] or Decimal('0')
    except Exception:
        pass

    history = []
    for t in Transaction.objects.filter(
        transaction_type__in=['BOOST_PAYMENT', 'MISSION_PAYMENT'],
    ).select_related('wallet__user').order_by('-created_at')[:30]:
        history.append({
            'id': str(t.id),
            'type': t.transaction_type,
            'amount': float(t.amount),
            'description': t.description[:80] if t.description else '',
            'created_at': t.created_at.strftime('%Y-%m-%d %H:%M'),
        })

    return Response({
        'platform_revenue': float(platform_revenue),
        'boost_revenue': float(boost_revenue),
        'escrow_held': float(escrow_held),
        'influencer_pending': float(influencer_pending),
        'available_estimate': float(platform_revenue + boost_revenue),
        'history': history,
    })


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

