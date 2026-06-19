from rest_framework import viewsets, permissions, status, pagination
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Count, Sum, Avg, Q
from django.db import transaction
from datetime import datetime, timedelta
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
import json
import os
import uuid
from decimal import Decimal
from .models import Mission, MissionProof, MissionTimelineEvent, AgentStatistics, MaterialWithdrawalRequest
from .serializers import (
    MissionProofSerializer, MissionProofCreateSerializer,
    MissionTimelineEventSerializer, MissionTimelineEventCreateSerializer,
    AgentStatisticsSerializer, AgentDashboardStatsSerializer,
    MissionProofBulkCreateSerializer, MissionDetailSerializer, MissionCreateSerializer,
)
from apps.escrow.services import EscrowService
from apps.core.choices import EscrowStatus
from apps.chat.views import send_system_message
from apps.notifications.services import NotificationService
from django.contrib.auth import get_user_model

User = get_user_model()


class MissionPagination(pagination.PageNumberPagination):
    """Pagination personnalisée pour les missions (20 par page)"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

_STATUS_EVENT_MAP = {
    'ON_THE_WAY': 'agent_en_route',
    'ARRIVED': 'agent_arrived',
    'IN_PROGRESS': 'in_progress',
    'IN_PROGRESS_REVIEW': 'proofs_uploaded',
    'COMPLETED': 'completed',
    'CANCELLED': 'cancelled',
    'ACCEPTED': 'accepted',
    'PENDING': 'created',
    'DISPUTED': 'disputed',
}

# Transitions autorisées (machine à états stricte, pas de retour en arrière).
_MISSION_TRANSITIONS = {
    'ACCEPTED': {'ON_THE_WAY'},
    'ON_THE_WAY': {'ARRIVED'},
    'ARRIVED': {'IN_PROGRESS'},
}


def _update_agent_geo(user, request_data):
    """Met à jour la position GPS de l'agent si fournie."""
    lat = request_data.get('latitude')
    lng = request_data.get('longitude')
    if lat is None or lng is None:
        return
    try:
        user.latitude = float(lat)
        user.longitude = float(lng)
        user.save(update_fields=['latitude', 'longitude', 'updated_at'])
    except (TypeError, ValueError):
        pass


def _validate_mission_transition(current_status, new_status):
    allowed = _MISSION_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        return (
            f'Transition invalide : impossible de passer de {current_status} '
            f'à {new_status}.'
        )
    return None


def _agent_kyc_approved(user):
    """
    Règle KYC stricte FONACO :
    - Un agent dont AgentProfile.kyc_status != APPROVED ne peut pas accepter de missions (HTTP 403).
    - Côté Flutter : redirection vers KycLockScreen après connexion si isKycLocked.
    - Les listes « available » / « assigned » renvoient des résultats vides tant que le KYC n'est pas approuvé.
    """
    from apps.accounts.models import AgentProfile
    from apps.core.choices import AgentKYCStatus
    if not getattr(user, 'is_agent', False):
        return False
    profile, _ = AgentProfile.objects.get_or_create(user=user)
    return profile.kyc_status == AgentKYCStatus.APPROVED


def _agent_has_active_boost(user):
    from apps.boosts.models import AgentBoost
    now = timezone.now()
    return AgentBoost.objects.filter(
        agent=user,
        status='active',
        expires_at__gt=now,
    ).exists()


_ACTIVE_MISSION_STATUSES = (
    'ACCEPTED',
    'ON_THE_WAY',
    'ARRIVED',
    'IN_PROGRESS',
    'IN_PROGRESS_REVIEW',
)


def _count_agent_active_missions(user):
    return Mission.objects.filter(
        agent=user,
        status__in=_ACTIVE_MISSION_STATUSES,
    ).count()


def _agent_completed_missions_count(user):
    return Mission.objects.filter(agent=user, status='COMPLETED').count()


def _agent_mission_capacity(user):
    """Limite de missions simultanées selon profil agent."""
    if _agent_has_active_boost(user):
        return 5
    if _agent_completed_missions_count(user) >= 50:
        return 3
    return 1


def _agent_can_accept_more(user):
    return _count_agent_active_missions(user) < _agent_mission_capacity(user)


def _notify_agents_new_mission(mission):
    """Push FCM + notification in-app aux agents KYC approuvés."""
    from apps.accounts.models import AgentProfile
    from apps.core.choices import AgentKYCStatus
    from apps.core.services import PlatformConfigService

    delay_min = PlatformConfigService.agent_mission_delay_minutes()
    title = 'Nouvelle mission disponible'
    body = (
        f'{mission.title[:100]} — visible dans votre panier '
        f'dans {delay_min} min (priorité boost).'
    )
    data = {
        'type': 'NEW_MISSION',
        'mission_id': str(mission.id),
        'delay_minutes': str(delay_min),
    }
    agents = User.objects.filter(is_agent=True, is_active=True)
    for agent in agents:
        profile, _ = AgentProfile.objects.get_or_create(user=agent)
        if profile.kyc_status != AgentKYCStatus.APPROVED:
            continue
        NotificationService.send_to_user(agent, title, body, data=data)
        NotificationService.create_in_app_notification(agent, title, body, data=data)


def _notify_mission_event(user, title, body, event_type, mission_id):
    """Push FCM + notification in-app pour un événement mission."""
    if not user:
        return
    data = {
        'type': event_type,
        'mission_id': str(mission_id),
    }
    NotificationService.send_to_user(user, title, body, data=data)
    NotificationService.create_in_app_notification(user, title, body, data=data)


class MissionViewSet(viewsets.ViewSet):
    """CRUD principal des missions + actions métier."""
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = MissionPagination

    def _get_mission(self, pk, user):
        """Récupère une mission et vérifie que l'utilisateur est client ou agent."""
        mission = get_object_or_404(Mission, pk=pk)
        if mission.client != user and mission.agent != user:
            return None, Response(
                {'status': 'error', 'message': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return mission, None

    def _log_event(self, mission, event_type, user, request_data=None):
        request_data = request_data or {}
        MissionTimelineEvent.objects.create(
            mission=mission,
            event_type=event_type,
            performed_by=user,
            location_lat=request_data.get('latitude'),
            location_lng=request_data.get('longitude'),
            notes=request_data.get('notes', ''),
        )

    # ------------------------------------------------------------------
    # Standard CRUD
    # ------------------------------------------------------------------

    def list(self, request):
        user = request.user
        if user.is_agent:
            qs = Mission.objects.filter(
                status='PENDING', agent__isnull=True
            ).select_related('client', 'agent').order_by('-created_at')
        else:
            qs = Mission.objects.filter(client=user).select_related('client', 'agent').order_by('-created_at')

        # Apply pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            serializer = MissionDetailSerializer(page, many=True, context={'request': request})
            return Response({
                'status': 'success',
                'message': 'Missions récupérées',
                'data': paginator.get_paginated_response(serializer.data).data
            })
        
        serializer = MissionDetailSerializer(qs, many=True, context={'request': request})
        return Response({
            'status': 'success',
            'message': 'Missions récupérées',
            'data': {'results': serializer.data}
        })

    def retrieve(self, request, pk=None):
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        return Response(MissionDetailSerializer(mission, context={'request': request}).data)

    def create(self, request):
        serializer = MissionCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            mission = serializer.save()
            self._log_event(mission, 'created', request.user)
            _notify_agents_new_mission(mission)
            try:
                from apps.missions.tasks import check_pending_mission_alert
                check_pending_mission_alert.apply_async(
                    args=[str(mission.id)],
                    countdown=300,
                )
            except Exception:
                pass
            return Response(MissionDetailSerializer(mission, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # ------------------------------------------------------------------
    # Custom list actions
    # ------------------------------------------------------------------

    @action(detail=False, methods=['get'])
    def available(self, request):
        """Missions PENDING sans agent — filtre boost 10 min, géo et zone."""
        user = request.user
        if not getattr(user, 'is_agent', False):
            return Response(
                {'message': 'Réservé aux agents'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _agent_kyc_approved(user):
            return Response({'results': []})

        qs = Mission.objects.filter(status='PENDING', agent__isnull=True).filter(
            Q(target_agent_username__isnull=True) | Q(target_agent_username='')
        )
        now = timezone.now()
        from apps.core.services import PlatformConfigService

        delay_min = PlatformConfigService.agent_mission_delay_minutes()
        cutoff = now - timedelta(minutes=delay_min)
        has_boost = _agent_has_active_boost(user)

        if not has_boost and delay_min > 0:
            qs = qs.filter(created_at__lte=cutoff)

        filter_by_zone = str(
            request.query_params.get('filter_by_zone', 'false')
        ).lower() in ('true', '1', 'yes')
        if filter_by_zone and user.city:
            qs = qs.filter(address__icontains=user.city.strip())

        lat = request.query_params.get('latitude')
        lng = request.query_params.get('longitude')
        if lat and lng and not filter_by_zone:
            try:
                from django.contrib.gis.geos import Point
                from django.contrib.gis.db.models.functions import Distance

                user_point = Point(float(lng), float(lat), srid=4326)
                radius_m = float(request.query_params.get('radius', 50000))
                qs = qs.annotate(
                    distance=Distance('location', user_point)
                ).filter(distance__lte=radius_m).order_by('distance')
            except (TypeError, ValueError):
                qs = qs.order_by('-created_at')
        else:
            qs = qs.order_by('-created_at')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            serializer = MissionDetailSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)

        serializer = MissionDetailSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def assigned(self, request):
        """Missions PENDING assignées explicitement à l'agent connecté."""
        user = request.user
        if not getattr(user, 'is_agent', False):
            return Response(
                {'message': 'Réservé aux agents'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _agent_kyc_approved(user):
            return Response({'results': []})

        username = (user.username or '').strip()
        if not username:
            return Response({'results': []})

        qs = Mission.objects.filter(
            status='PENDING',
            agent__isnull=True,
            target_agent_username__iexact=username,
        ).order_by('-created_at')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            serializer = MissionDetailSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)

        serializer = MissionDetailSerializer(qs, many=True, context={'request': request})
        return Response({'results': serializer.data})

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Missions acceptées / en cours pour l'agent connecté."""
        user = request.user
        if not getattr(user, 'is_agent', False):
            return Response(
                {'message': 'Réservé aux agents'},
                status=status.HTTP_403_FORBIDDEN,
            )
        active_statuses = [
            'ACCEPTED',
            'ON_THE_WAY',
            'ARRIVED',
            'IN_PROGRESS',
            'IN_PROGRESS_REVIEW',
        ]
        qs = Mission.objects.filter(
            agent=user,
            status__in=active_statuses,
        ).order_by('-updated_at')
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            serializer = MissionDetailSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        serializer = MissionDetailSerializer(qs, many=True, context={'request': request})
        return Response({'results': serializer.data})

    @action(detail=False, methods=['get'])
    def history(self, request):
        """Historique des missions complètes/annulées de l'agent."""
        limit = int(request.query_params.get('limit', 20))
        qs = Mission.objects.filter(
            agent=request.user,
            status__in=['COMPLETED', 'CANCELLED'],
        ).order_by('-updated_at')[:limit]
        return Response({'results': MissionDetailSerializer(qs, many=True, context={'request': request}).data})

    @action(detail=False, methods=['get'])
    def disputes(self, request):
        """Missions en litige pour l'agent connecté."""
        user = request.user
        if not getattr(user, 'is_agent', False):
            return Response(
                {'message': 'Réservé aux agents'},
                status=status.HTTP_403_FORBIDDEN,
            )
        limit = int(request.query_params.get('limit', 50))
        qs = Mission.objects.filter(
            agent=user,
            status='DISPUTED',
        ).order_by('-updated_at')[:limit]
        return Response({'results': MissionDetailSerializer(qs, many=True, context={'request': request}).data})

    # ------------------------------------------------------------------
    # Custom detail actions
    # ------------------------------------------------------------------

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        if not getattr(request.user, 'is_agent', False):
            return Response(
                {'status': 'error', 'message': 'Seuls les agents peuvent accepter une mission'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _agent_kyc_approved(request.user):
            return Response(
                {'message': 'Compte en attente de validation KYC.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _agent_can_accept_more(request.user):
            capacity = _agent_mission_capacity(request.user)
            return Response(
                {
                    'message': (
                        f'Limite atteinte : vous ne pouvez pas dépasser '
                        f'{capacity} mission(s) active(s) simultanément.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            with transaction.atomic():
                mission = Mission.objects.select_for_update().get(pk=pk)
                if mission.client == request.user:
                    return Response(
                        {'status': 'error', 'message': 'Un agent ne peut pas accepter sa propre mission'},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                if mission.status != 'PENDING' or mission.agent_id is not None:
                    return Response(
                        {
                            'message': (
                                'Cette mission a déjà été acceptée par un autre agent.'
                            ),
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                reserved_for = (mission.target_agent_username or '').strip()
                if reserved_for and reserved_for.lower() != (request.user.username or '').lower():
                    return Response(
                        {'message': 'Cette mission est réservée à un autre agent.'},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                mission.agent = request.user
                mission.status = 'ACCEPTED'
                if mission.target_agent_username:
                    mission.target_agent_username = None
                mission.save(update_fields=['agent', 'status', 'target_agent_username', 'updated_at'])
                EscrowService.lock_on_accept(mission)
                # Matériel : libéré uniquement après validation admin (MaterialWithdrawalRequest)
                if _mission_material_cost(mission) <= 0:
                    EscrowService.release_purchase_to_agent(mission)
        except Mission.DoesNotExist:
            return Response({'status': 'error', 'message': 'Mission introuvable'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        self._log_event(mission, 'accepted', request.user)
        send_system_message(mission, f"Mission acceptée par {request.user.username}")
        _notify_mission_event(
            mission.client,
            'Mission acceptée',
            f'Un agent a accepté votre mission « {mission.title[:80]} ».',
            'MISSION_ACCEPTED',
            mission.id,
        )
        return Response(MissionDetailSerializer(mission, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='request_material_funds')
    def request_material_funds(self, request, pk=None):
        """Demande de déblocage des fonds matériel (validation admin requise)."""
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        if mission.agent != request.user:
            return Response(
                {'message': 'Réservé à l\'agent assigné'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if mission.material_released:
            return Response(
                {'message': 'Les fonds matériel ont déjà été libérés'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if MaterialWithdrawalRequest.objects.filter(
            mission=mission,
            status=MaterialWithdrawalRequest.Status.PENDING,
        ).exists():
            return Response(
                {'message': 'Une demande est déjà en cours de traitement'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_amount = request.data.get('amount')
        if raw_amount is not None:
            try:
                amount = Decimal(str(raw_amount))
            except (TypeError, ValueError, ArithmeticError):
                return Response(
                    {'message': 'Montant invalide'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            amount = mission.material_cost or mission.purchase_amount or Decimal('0')

        if amount <= 0:
            return Response(
                {'message': 'Aucun montant matériel défini pour cette mission'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        withdrawal = MaterialWithdrawalRequest.objects.create(
            mission=mission,
            amount=amount,
        )
        return Response(
            {
                'id': withdrawal.id,
                'status': withdrawal.status,
                'amount': float(withdrawal.amount),
                'message': 'Demande envoyée — en attente de validation admin',
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='decline_assignment')
    def decline_assignment(self, request, pk=None):
        """Refus d'une mission assignée manuellement à l'agent."""
        if not getattr(request.user, 'is_agent', False):
            return Response(
                {'status': 'error', 'message': 'Réservé aux agents'},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            mission = Mission.objects.get(pk=pk)
        except Mission.DoesNotExist:
            return Response(
                {'status': 'error', 'message': 'Mission introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )

        target = (mission.target_agent_username or '').strip()
        username = (request.user.username or '').strip()
        if not target or target.lower() != username.lower():
            return Response(
                {
                    'status': 'error',
                    'message': 'Cette mission ne vous a pas été assignée',
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if mission.status != 'PENDING' or mission.agent_id is not None:
            return Response(
                {'status': 'error', 'message': 'Mission non refusable'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mission.target_agent_username = None
        mission.save(update_fields=['target_agent_username', 'updated_at'])
        send_system_message(
            mission,
            f"{request.user.username} a refusé la mission assignée",
        )
        return Response(MissionDetailSerializer(mission, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def start_mission(self, request, pk=None):
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        if mission.agent != request.user:
            return Response({'status': 'error', 'message': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)

        transition_error = _validate_mission_transition(mission.status, 'IN_PROGRESS')
        if transition_error:
            return Response({'message': transition_error}, status=status.HTTP_400_BAD_REQUEST)

        _update_agent_geo(request.user, request.data)
        mission.status = 'IN_PROGRESS'
        mission.save(update_fields=['status', 'updated_at'])
        self._log_event(mission, 'in_progress', request.user, request.data)
        send_system_message(mission, "La mission a démarré")
        return Response(MissionDetailSerializer(mission, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def mark_completed_live(self, request, pk=None):
        """Agent : clôture live sans photo — passe en IN_PROGRESS_REVIEW."""
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        if mission.agent != request.user:
            return Response(
                {'status': 'error', 'message': 'Non autorisé'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if mission.status != 'IN_PROGRESS':
            return Response(
                {
                    'message': (
                        'La mission doit être en cours (IN_PROGRESS) '
                        'pour être marquée terminée.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        _update_agent_geo(request.user, request.data)
        mission.status = 'IN_PROGRESS_REVIEW'
        mission.save(update_fields=['status', 'updated_at'])
        self._log_event(mission, 'proofs_uploaded', request.user, request.data)
        send_system_message(
            mission,
            "Mission marquée terminée — en attente de validation client.",
        )
        _notify_mission_event(
            mission.client,
            'Validation requise',
            (
                f'L\'agent a terminé la mission « {mission.title[:80]} ». '
                'Validez pour libérer les fonds.'
            ),
            'MISSION_PROOF_SUBMITTED',
            mission.id,
        )
        return Response(MissionDetailSerializer(mission, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def update_steps(self, request, pk=None):
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        if mission.agent != request.user:
            return Response(
                {'message': 'Non autorisé'},
                status=status.HTTP_403_FORBIDDEN,
            )

        new_status = request.data.get('status')
        if not new_status:
            return Response(
                {'message': 'Le statut est requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_status = str(new_status).upper()
        _ALLOWED_TARGET_STATUSES = {'ON_THE_WAY', 'ARRIVED', 'IN_PROGRESS'}
        if new_status not in _ALLOWED_TARGET_STATUSES:
            return Response(
                {
                    'message': (
                        f'Statut invalide. Valeurs acceptées : '
                        f'{", ".join(sorted(_ALLOWED_TARGET_STATUSES))}'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        transition_error = _validate_mission_transition(mission.status, new_status)
        if transition_error:
            return Response({'message': transition_error}, status=status.HTTP_400_BAD_REQUEST)

        _update_agent_geo(request.user, request.data)
        mission.status = new_status
        mission.save(update_fields=['status', 'updated_at'])
        self._log_event(mission, _STATUS_EVENT_MAP[new_status], request.user, request.data)
        _sys_msgs = {
            'ON_THE_WAY': "L'agent est en route",
            'ARRIVED': "L'agent est arrivé",
            'IN_PROGRESS': 'La mission est en cours',
        }
        send_system_message(mission, _sys_msgs.get(new_status, new_status))
        return Response(MissionDetailSerializer(mission, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def submit_completion(self, request, pk=None):
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        if mission.agent != request.user:
            return Response(
                {'message': 'Non autorisé'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if mission.status != 'IN_PROGRESS':
            return Response(
                {
                    'message': (
                        'La mission doit être en cours (IN_PROGRESS) '
                        'pour soumettre une preuve.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        proof_file = request.FILES.get('completion_proof')
        if not proof_file:
            return Response(
                {'message': 'La photo de preuve (completion_proof) est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _update_agent_geo(request.user, request.data)
        mission.end_photo = proof_file
        mission.status = 'IN_PROGRESS_REVIEW'
        mission.save(update_fields=['status', 'end_photo', 'updated_at'])

        MissionProof.objects.create(
            mission=mission,
            uploaded_by=request.user,
            image=proof_file,
            caption='Preuve de complétion',
            is_primary=True,
            location_lat=request.data.get('latitude'),
            location_lng=request.data.get('longitude'),
        )

        self._log_event(mission, 'proofs_uploaded', request.user, request.data)
        send_system_message(
            mission,
            "L'agent a soumis les preuves — en attente de validation client.",
        )
        _notify_mission_event(
            mission.client,
            'Validation requise',
            (
                f'L\'agent a terminé la mission « {mission.title[:80]} ». '
                'Validez la preuve pour libérer les fonds.'
            ),
            'MISSION_PROOF_SUBMITTED',
            mission.id,
        )
        return Response(MissionDetailSerializer(mission, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def validate_completion(self, request, pk=None):
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        if mission.status not in ('IN_PROGRESS_REVIEW', 'IN_PROGRESS'):
            return Response(
                {'status': 'error', 'message': 'Mission non éligible à la validation.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_client = mission.client == request.user
        qr_data = request.data.get('qr_code_data', '')
        if not is_client:
            if mission.qr_code_token != qr_data:
                return Response(
                    {'status': 'error', 'message': 'QR Code invalide'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif mission.status != 'IN_PROGRESS_REVIEW':
            return Response(
                {
                    'status': 'error',
                    'message': 'En attente de la preuve de complétion de l\'agent.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            EscrowService.release_to_agent(mission)
        except ValueError as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mission.status = 'COMPLETED'
        mission.qr_code_token = uuid.uuid4().hex
        mission.save(update_fields=['status', 'qr_code_token', 'updated_at'])
        self._log_event(mission, 'validated', request.user)
        send_system_message(mission, "Mission validée — fonds libérés vers l'agent")
        return Response({
            'status': 'success',
            'message': 'Mission validée et fonds libérés',
            'data': MissionDetailSerializer(mission, context={'request': request}).data,
        })

    @action(detail=True, methods=['post'], url_path='release_funds')
    def release_funds(self, request, pk=None):
        """Alias client : finalise la mission et libère l'escrow."""
        return self.validate_completion(request, pk=pk)

    @action(detail=True, methods=['post'], url_path='allow_price_negotiation')
    def allow_price_negotiation(self, request, pk=None):
        """Le client autorise l'agent à proposer un nouveau tarif."""
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        if mission.client != request.user:
            return Response(
                {'status': 'error', 'message': 'Réservé au client'},
                status=status.HTTP_403_FORBIDDEN,
            )
        allowed = bool(request.data.get('allowed', True))
        mission.price_negotiation_allowed = allowed
        mission.save(update_fields=['price_negotiation_allowed', 'updated_at'])
        msg = (
            'Le client autorise une proposition de tarif.'
            if allowed else 'Proposition de tarif désactivée.'
        )
        send_system_message(mission, msg)
        return Response({
            'status': 'success',
            'price_negotiation_allowed': allowed,
            'data': MissionDetailSerializer(mission, context={'request': request}).data,
        })

    @action(detail=True, methods=['post'])
    def open_dispute(self, request, pk=None):
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        reason = request.data.get('reason', '')
        description = request.data.get('description', '')
        evidence_file = request.FILES.get('evidence_file')
        with transaction.atomic():
            mission.status = 'DISPUTED'
            mission.save(update_fields=['status', 'updated_at'])
            from apps.disputes.models import Dispute as DisputeRecord
            dispute = DisputeRecord.objects.create(
                mission=mission,
                opened_by=request.user,
                title=reason or 'Litige',
                description=description or reason,
                priority='medium',
            )
            if evidence_file:
                dispute.evidence_file = evidence_file
                dispute.save(update_fields=['evidence_file'])
        self._log_event(mission, 'disputed', request.user, {'notes': f'{reason}: {description}'})
        return Response({'status': 'success', 'message': 'Litige ouvert'})

    @action(detail=True, methods=['post'])
    def cancel_mission(self, request, pk=None):
        """Annule une mission. Dédommagement 20 % agent si mission déjà acceptée."""
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err

        if mission.client != request.user:
            return Response(
                {'status': 'error', 'message': 'Seul le client peut annuler la mission'},
                status=status.HTTP_403_FORBIDDEN,
            )

        cancellable = {'ACCEPTED', 'ON_THE_WAY', 'ARRIVED', 'IN_PROGRESS', 'PENDING'}
        if mission.status not in cancellable:
            return Response(
                {'status': 'error', 'message': 'Cette mission ne peut pas être annulée'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        compensated_statuses = {'ACCEPTED', 'ON_THE_WAY', 'ARRIVED', 'IN_PROGRESS'}
        try:
            with transaction.atomic():
                if mission.status == 'PENDING' and not mission.agent_id:
                    mission.target_agent_username = None
                    if hasattr(mission, 'escrow') and mission.escrow.status == EscrowStatus.HELD:
                        EscrowService.refund_to_client(mission, reason='Annulation gratuite (en attente)')
                elif mission.status in compensated_statuses and mission.agent_id:
                    EscrowService.cancel_with_agent_compensation(mission)
                elif hasattr(mission, 'escrow') and mission.escrow.status == EscrowStatus.HELD:
                    EscrowService.refund_to_client(mission, reason='Annulation mission')

                mission.status = 'CANCELLED'
                mission.save(update_fields=['status', 'target_agent_username', 'updated_at'])
        except ValueError as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        self._log_event(mission, 'cancelled', request.user)
        send_system_message(mission, 'La mission a été annulée par le client')
        return Response({
            'status': 'success',
            'message': 'Mission annulée',
            'data': MissionDetailSerializer(mission, context={'request': request}).data,
        })

    @action(detail=True, methods=['post'], url_path='update_negotiated_price')
    def update_negotiated_price(self, request, pk=None):
        """Accepte une proposition tarifaire et applique l'avenant après paiement."""
        from decimal import Decimal
        from apps.chat.models import Message

        mission, err = self._get_mission(pk, request.user)
        if err:
            return err

        if mission.client != request.user:
            return Response(
                {'status': 'error', 'message': 'Seul le client peut accepter un tarif'},
                status=status.HTTP_403_FORBIDDEN,
            )

        message_id = request.data.get('message_id')
        payment_method = (request.data.get('payment_method') or 'wallet').lower()
        payment_reference = request.data.get('payment_reference')

        if not message_id:
            return Response(
                {'status': 'error', 'message': 'message_id requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                message = Message.objects.select_for_update().get(
                    id=message_id,
                    conversation__mission=mission,
                    message_type='negotiation',
                )

                if message.negotiation_status != Message.NegotiationStatus.PENDING:
                    return Response(
                        {
                            'status': 'error',
                            'message': 'Cette proposition a déjà été traitée',
                            'negotiation_status': message.negotiation_status,
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                proposed = Decimal(message.proposed_price or 0)
                if proposed <= 0:
                    return Response(
                        {'status': 'error', 'message': 'Montant proposé invalide'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                current = Decimal(
                    mission.service_amount if mission.service_amount and mission.service_amount > 0
                    else mission.price
                )
                delta = proposed - current

                if delta > 0:
                    if payment_method == 'wallet':
                        EscrowService.apply_negotiated_price_increase(mission, delta)
                    elif payment_method == 'feexpay':
                        if not payment_reference:
                            return Response(
                                {
                                    'status': 'error',
                                    'message': 'Référence de paiement FeexPay requise',
                                },
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                        EscrowService.apply_negotiated_price_increase(mission, delta)
                    else:
                        return Response(
                            {'status': 'error', 'message': 'Méthode de paiement invalide'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                mission.service_amount = proposed
                mission.price = proposed
                mission.save(update_fields=['service_amount', 'price', 'updated_at'])

                message.negotiation_status = Message.NegotiationStatus.ACCEPTED
                message.save(update_fields=['negotiation_status'])

        except Message.DoesNotExist:
            return Response(
                {'status': 'error', 'message': 'Message de négociation introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mission.refresh_from_db()
        send_system_message(
            mission,
            f'Tarif accepté : {proposed:.0f} FCFA',
        )
        return Response({
            'status': 'success',
            'message': 'Tarif négocié appliqué',
            'data': MissionDetailSerializer(mission, context={'request': request}).data,
            'negotiation_status': Message.NegotiationStatus.ACCEPTED,
        })

    @action(detail=True, methods=['post'], url_path='reject_negotiation')
    def reject_negotiation(self, request, pk=None):
        """Refuse une proposition tarifaire (idempotent si déjà traitée)."""
        from apps.chat.models import Message

        mission, err = self._get_mission(pk, request.user)
        if err:
            return err

        if mission.client != request.user:
            return Response(
                {'status': 'error', 'message': 'Seul le client peut refuser un tarif'},
                status=status.HTTP_403_FORBIDDEN,
            )

        message_id = request.data.get('message_id')
        if not message_id:
            return Response(
                {'status': 'error', 'message': 'message_id requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                message = Message.objects.select_for_update().get(
                    id=message_id,
                    conversation__mission=mission,
                    message_type='negotiation',
                )

                if message.negotiation_status == Message.NegotiationStatus.ACCEPTED:
                    return Response(
                        {'status': 'error', 'message': 'Proposition déjà acceptée'},
                        status=status.HTTP_409_CONFLICT,
                    )

                if message.negotiation_status != Message.NegotiationStatus.REJECTED:
                    message.negotiation_status = Message.NegotiationStatus.REJECTED
                    message.save(update_fields=['negotiation_status'])

        except Message.DoesNotExist:
            return Response(
                {'status': 'error', 'message': 'Message de négociation introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            'status': 'success',
            'message': 'Proposition refusée',
            'negotiation_status': Message.NegotiationStatus.REJECTED,
        })

    @action(detail=True, methods=['post'])
    def rate_client(self, request, pk=None):
        """Permet à l'agent de noter le client après mission terminée"""
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        
        if mission.agent != request.user:
            return Response(
                {'status': 'error', 'message': 'Seul l\'agent assigné peut noter le client'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if mission.status != 'COMPLETED':
            return Response(
                {'status': 'error', 'message': 'La mission doit être terminée pour noter'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        rating = request.data.get('rating')
        comment = request.data.get('comment', '')
        
        if not rating or not (1 <= rating <= 5):
            return Response(
                {'status': 'error', 'message': 'La note doit être entre 1 et 5'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        mission.agent_rating = rating
        mission.agent_comment = comment
        mission.save(update_fields=['agent_rating', 'agent_comment', 'updated_at'])
        
        return Response({
            'status': 'success',
            'message': 'Client noté avec succès',
            'data': {
                'agent_rating': mission.agent_rating,
                'agent_comment': mission.agent_comment
            }
        })

    @action(detail=True, methods=['post'])
    def manual_remote_validation(self, request, pk=None):
        """Validation manuelle distante par le client (sans QR Code)"""
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        
        if mission.client != request.user:
            return Response(
                {'status': 'error', 'message': 'Seul le client peut valider la mission'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if mission.status not in ['IN_PROGRESS', 'ON_THE_WAY', 'ARRIVED', 'COMPLETED']:
            return Response(
                {'status': 'error', 'message': 'La mission doit être en cours ou terminée pour libérer les fonds'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return self.release_funds(request, pk=pk)

    @action(detail=True, methods=['post'])
    def release_funds(self, request, pk=None):
        """Libère les fonds de l'escrow vers l'agent (validation client sans QR)."""
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err

        if mission.client != request.user:
            return Response(
                {'status': 'error', 'message': 'Seul le client peut libérer les fonds'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if mission.status not in ['IN_PROGRESS', 'ON_THE_WAY', 'ARRIVED', 'COMPLETED']:
            return Response(
                {'status': 'error', 'message': 'La mission doit être en cours ou terminée pour libérer les fonds'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            EscrowService.release_to_agent(mission)
        except ValueError as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mission.status = 'COMPLETED'
        mission.save(update_fields=['status', 'updated_at'])
        self._log_event(mission, 'validated_remotely', request.user)

        return Response({
            'status': 'success',
            'message': 'Fonds libérés et mission validée',
            'data': MissionDetailSerializer(mission, context={'request': request}).data,
        })

    @action(detail=True, methods=['post'])
    def rate(self, request, pk=None):
        """Permet au client de noter l'agent après mission terminée."""
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err

        if mission.client != request.user:
            return Response(
                {'status': 'error', 'message': 'Seul le client peut noter l\'agent'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if mission.status != 'COMPLETED':
            return Response(
                {'status': 'error', 'message': 'La mission doit être terminée pour noter'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rating = request.data.get('rating')
        comment = request.data.get('comment', '')

        if not rating or not (1 <= int(rating) <= 5):
            return Response(
                {'status': 'error', 'message': 'La note doit être entre 1 et 5'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mission.client_rating = int(rating)
        mission.client_comment = comment
        mission.save(update_fields=['client_rating', 'client_comment', 'updated_at'])

        return Response({
            'status': 'success',
            'message': 'Agent noté avec succès',
            'data': {
                'client_rating': mission.client_rating,
                'client_comment': mission.client_comment,
            },
        })

    @action(detail=True, methods=['get'])
    def invoice(self, request, pk=None):
        """Génère une facture PDF pour une mission"""
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        
        # Permettre le téléchargement même pour les missions non terminées (dev)
        # if mission.status != 'COMPLETED':
        #     return Response(
        #         {'status': 'error', 'message': 'La facture n\'est disponible que pour les missions terminées'},
        #         status=status.HTTP_400_BAD_REQUEST
        #     )
        
        from decimal import Decimal

        response = HttpResponse(content_type='application/pdf')
        invoice_number = f"INV-{mission.created_at.strftime('%Y%m%d')}-{str(mission.id)[:8]}"
        response['Content-Disposition'] = f'attachment; filename="facture_{invoice_number}.pdf"'

        from apps.core.services import (
            FEES_CONFIDENTIAL_KEY,
            FEES_URGENT_KEY,
            PlatformConfigService,
        )

        doc = SimpleDocTemplate(
            response, pagesize=letter,
            topMargin=0.5 * inch, bottomMargin=0.5 * inch,
            leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        )
        elements = []
        styles = getSampleStyleSheet()
        urgent_fee = PlatformConfigService.get_decimal(FEES_URGENT_KEY, '500')
        confidential_fee = PlatformConfigService.get_decimal(FEES_CONFIDENTIAL_KEY, '500')

        header_row = Table(
            [[
                Paragraph(
                    '<b>Fonaqo</b>',
                    ParagraphStyle('Brand', parent=styles['Normal'], fontSize=20,
                                   textColor=colors.HexColor('#1a1a2e')),
                ),
                Paragraph(
                    f'Facture N° {invoice_number}<br/>'
                    f'{timezone.now().strftime("%d/%m/%Y")}',
                    ParagraphStyle('InvMeta', parent=styles['Normal'], fontSize=9,
                                   alignment=2, textColor=colors.grey),
                ),
            ]],
            colWidths=[3.5 * inch, 3 * inch],
        )
        header_row.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(header_row)
        elements.append(Spacer(1, 0.08 * inch))

        yellow_band = Table([['']], colWidths=[6.5 * inch], rowHeights=[4])
        yellow_band.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFD400')),
        ]))
        elements.append(yellow_band)
        elements.append(Spacer(1, 0.2 * inch))

        client_name = (
            f"{mission.client.first_name or ''} {mission.client.last_name or ''}".strip()
            or mission.client.username
        )
        if mission.agent:
            agent_name = (
                f"{mission.agent.first_name or ''} {mission.agent.last_name or ''}".strip()
                or mission.agent.username
            )
            agent_phone = mission.agent.phone_number or '—'
            agent_email = mission.agent.email or '—'
        else:
            agent_name = 'Non assigné'
            agent_phone = '—'
            agent_email = '—'

        party_style = ParagraphStyle(
            'Party', parent=styles['Normal'], fontSize=9, leading=13,
        )
        parties = Table(
            [[
                Paragraph(
                    f'<b>AGENT</b><br/>{agent_name}<br/>'
                    f'Contact : {agent_phone}<br/>Email : {agent_email}',
                    party_style,
                ),
                Paragraph(
                    f'<b>FACTURÉ À</b><br/>{client_name}<br/>'
                    f'Contact : {mission.client.phone_number or "—"}<br/>'
                    f'Email : {mission.client.email or "—"}',
                    party_style,
                ),
            ]],
            colWidths=[3.2 * inch, 3.2 * inch],
        )
        parties.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        elements.append(parties)
        elements.append(Spacer(1, 0.25 * inch))

        first_tag = mission.tags.first() if hasattr(mission, 'tags') else None
        category_name = first_tag.name if first_tag else 'Service'
        service_amount = Decimal(mission.service_amount or mission.price or 0)

        if getattr(mission, 'is_vocal_description', False):
            desc_label = 'Description Vocale'
        else:
            desc_label = (mission.description or mission.title)[:120]

        table_data = [['Description', 'Catégorie', 'Montant (FCFA)']]
        table_data.append([desc_label, category_name, f'{float(service_amount):.0f}'])

        if mission.is_urgent:
            table_data.append(['Mission Urgente', 'Option', f'{float(urgent_fee):.0f}'])
        if mission.is_confidential:
            table_data.append(['Agent Interne Fonaqo', 'Option', f'{float(confidential_fee):.0f}'])

        platform_fee = Decimal(mission.service_fee or 0)
        platform_fee -= urgent_fee if mission.is_urgent else Decimal('0')
        platform_fee -= confidential_fee if mission.is_confidential else Decimal('0')
        if platform_fee < 0:
            platform_fee = Decimal('0')
        if platform_fee > 0:
            table_data.append(['Frais plateforme', 'FONACO', f'{float(platform_fee):.0f}'])

        purchase = Decimal(mission.purchase_amount or 0)
        if purchase > 0:
            table_data.append(['Montant achats', 'Achats', f'{float(purchase):.0f}'])

        total_ttc = sum(
            Decimal(str(row[2]).replace(' ', ''))
            for row in table_data[1:]
        )

        mission_table = Table(
            table_data,
            colWidths=[3.2 * inch, 1.6 * inch, 1.6 * inch],
        )
        mission_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFD400')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(mission_table)
        elements.append(Spacer(1, 0.2 * inch))

        total_row = Table(
            [['TOTAL TTC', f'{float(total_ttc):.0f} FCFA']],
            colWidths=[4.5 * inch, 2 * inch],
        )
        total_row.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFB800')),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(total_row)

        doc.build(elements)
        return response


class IsMissionParticipant(permissions.BasePermission):
    """Permission pour vérifier si l'utilisateur participe à la mission"""

    def has_object_permission(self, request, view, obj):
        user = request.user
        return obj.mission.client == user or obj.mission.agent == user


class MissionProofViewSet(viewsets.ModelViewSet):
    """ViewSet pour les preuves de mission"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_agent:
            return MissionProof.objects.filter(mission__agent=user)
        return MissionProof.objects.filter(mission__client=user)

    def get_serializer_class(self):
        if self.action == 'create':
            return MissionProofCreateSerializer
        return MissionProofSerializer

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Créer plusieurs preuves en une fois"""
        serializer = MissionProofBulkCreateSerializer(data=request.data)
        if serializer.is_valid():
            mission_id = serializer.validated_data['mission_id']
            proofs_data = serializer.validated_data['proofs']

            user = request.user
            if not user.is_agent:
                return Response(
                    {'error': 'Seuls les agents peuvent ajouter des preuves'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            created_proofs = []
            for proof_data in proofs_data:
                proof_serializer = MissionProofCreateSerializer(
                    data={
                        'mission': mission_id,
                        **proof_data
                    },
                    context={'request': request}
                )
                
                if proof_serializer.is_valid():
                    proof = proof_serializer.save(uploaded_by=user)
                    created_proofs.append(proof)
            
            return Response({
                'created_count': len(created_proofs),
                'proofs': MissionProofSerializer(created_proofs, many=True, context={'request': request}).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def set_primary(self, request, pk=None):
        """Définir une preuve comme principale"""
        proof = self.get_object()
        
        # Retirer le statut principal des autres preuves de cette mission
        MissionProof.objects.filter(mission=proof.mission, is_primary=True).update(is_primary=False)
        
        # Définir cette preuve comme principale
        proof.is_primary = True
        proof.save(update_fields=['is_primary'])
        
        return Response({
            'message': 'Preuve définie comme principale',
            'is_primary': True
        })


class MissionTimelineEventViewSet(viewsets.ModelViewSet):
    """ViewSet pour les événements de timeline"""
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_agent:
            return MissionTimelineEvent.objects.filter(mission__agent=user)
        return MissionTimelineEvent.objects.filter(mission__client=user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return MissionTimelineEventCreateSerializer
        return MissionTimelineEventSerializer
    
    def perform_create(self, serializer):
        serializer.save(performed_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def mission_timeline(self, request):
        """Obtenir la timeline complète d'une mission"""
        mission_id = request.query_params.get('mission_id')
        if not mission_id:
            return Response(
                {'error': 'mission_id requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        try:
            from apps.missions.models import Mission
            mission = Mission.objects.get(id=mission_id)

            if not (mission.client == user or mission.agent == user):
                return Response(
                    {'error': 'Permission refusée'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            events = MissionTimelineEvent.objects.filter(mission=mission).order_by('occurred_at')
            serializer = MissionTimelineEventSerializer(events, many=True, context={'request': request})
            
            return Response(serializer.data)
            
        except Mission.DoesNotExist:
            return Response(
                {'error': 'Mission introuvable'},
                status=status.HTTP_404_NOT_FOUND
            )


class AgentStatisticsViewSet(viewsets.ModelViewSet):
    """ViewSet pour les statistiques d'agent"""
    serializer_class = AgentStatisticsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_agent:
            return AgentStatistics.objects.filter(agent=user)
        return AgentStatistics.objects.none()

    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Statistiques du dashboard agent"""
        user = request.user
        if not user.is_agent:
            return Response({'error': 'Réservé aux agents'}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        # Optimisation: Query unique avec aggregations conditionnelles
        from django.db.models import Case, When, IntegerField, DecimalField

        missions_stats = Mission.objects.filter(agent=user).aggregate(
            total_missions=Count('id'),
            total_earnings=Sum(Case(
                When(status='COMPLETED', then='price'),
                default=0,
                output_field=DecimalField()
            )),
            completed_count=Count(Case(
                When(status='COMPLETED', then=1),
                output_field=IntegerField()
            )),
            active_missions=Count(Case(
                When(status__in=['ACCEPTED', 'ON_THE_WAY', 'IN_PROGRESS', 'ARRIVED', 'IN_PROGRESS_REVIEW'], then=1),
                output_field=IntegerField()
            )),
            pending_missions=Count(Case(
                When(status='PENDING', then=1),
                output_field=IntegerField()
            )),
            today_missions=Count(Case(
                When(updated_at__date=today, then=1),
                output_field=IntegerField()
            )),
            today_earnings=Sum(Case(
                When(status='COMPLETED', updated_at__date=today, then='price'),
                default=0,
                output_field=DecimalField()
            )),
            week_missions=Count(Case(
                When(updated_at__date__gte=week_start, then=1),
                output_field=IntegerField()
            )),
            week_earnings=Sum(Case(
                When(status='COMPLETED', updated_at__date__gte=week_start, then='price'),
                default=0,
                output_field=DecimalField()
            )),
            month_missions=Count(Case(
                When(updated_at__date__gte=month_start, then=1),
                output_field=IntegerField()
            )),
            month_earnings=Sum(Case(
                When(status='COMPLETED', updated_at__date__gte=month_start, then='price'),
                default=0,
                output_field=DecimalField()
            )),
        )

        total_missions = missions_stats['total_missions'] or 0
        total_earnings = missions_stats['total_earnings'] or 0
        completed_count = missions_stats['completed_count'] or 0
        completion_rate = round(completed_count / total_missions * 100, 2) if total_missions > 0 else 0

        stats, _ = AgentStatistics.objects.get_or_create(agent=user)

        dashboard_data = {
            'today_missions': missions_stats['today_missions'] or 0,
            'today_earnings': missions_stats['today_earnings'] or 0,
            'week_missions': missions_stats['week_missions'] or 0,
            'week_earnings': missions_stats['week_earnings'] or 0,
            'month_missions': missions_stats['month_missions'] or 0,
            'month_earnings': missions_stats['month_earnings'] or 0,
            'total_missions': total_missions,
            'total_earnings': total_earnings,
            'average_rating': float(stats.average_rating),
            'completion_rate': completion_rate,
            'active_missions': missions_stats['active_missions'] or 0,
            'pending_missions': missions_stats['pending_missions'] or 0,
            'level': 'NOVICE',
            'current_streak': stats.current_streak,
        }

        serializer = AgentDashboardStatsSerializer(dashboard_data)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def update_stats(self, request):
        """Mettre à jour les statistiques"""
        user = request.user
        if not user.is_agent:
            return Response({'error': 'Réservé aux agents'}, status=status.HTTP_403_FORBIDDEN)

        total_missions = Mission.objects.filter(agent=user).count()
        completed_missions = Mission.objects.filter(agent=user, status='COMPLETED').count()
        cancelled_missions = Mission.objects.filter(agent=user, status='CANCELLED').count()
        total_earnings = Mission.objects.filter(
            agent=user, status='COMPLETED'
        ).aggregate(total=Sum('price'))['total'] or 0

        stats, _ = AgentStatistics.objects.get_or_create(agent=user)
        stats.total_missions = total_missions
        stats.completed_missions = completed_missions
        stats.cancelled_missions = cancelled_missions
        stats.total_earnings = total_earnings
        stats.save(update_fields=['total_missions', 'completed_missions', 'cancelled_missions', 'total_earnings'])

        return Response({'message': 'Statistiques mises à jour', 'stats': AgentStatisticsSerializer(stats).data})

    @action(detail=False, methods=['get'], url_path='monthly_report', renderer_classes=[])
    def monthly_report(self, request):
        """PDF relevé mensuel agent (wallet + missions)."""
        user = request.user
        if not user.is_agent:
            return Response(
                {'message': 'Réservé aux agents'},
                status=status.HTTP_403_FORBIDDEN,
            )

        month_str = request.query_params.get('month') or timezone.now().strftime('%Y-%m')
        try:
            from datetime import datetime as dt
            year, month = map(int, month_str.split('-'))
            start_date = timezone.make_aware(dt(year, month, 1))
            if month == 12:
                end_date = timezone.make_aware(dt(year + 1, 1, 1))
            else:
                end_date = timezone.make_aware(dt(year, month + 1, 1))
        except (ValueError, IndexError):
            return Response(
                {'message': 'Format de mois invalide (YYYY-MM)'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.wallets.models import Wallet, Transaction as WalletTransaction
        from apps.missions.monthly_report_pdf import build_agent_monthly_report_pdf

        wallet = Wallet.objects.filter(user=user).first()
        transactions = []
        deposits = Decimal('0')
        withdrawals = Decimal('0')

        if wallet:
            transactions = list(
                WalletTransaction.objects.filter(
                    wallet=wallet,
                    created_at__gte=start_date,
                    created_at__lt=end_date,
                    status='COMPLETED',
                ).order_by('created_at')
            )
            for tx in transactions:
                amt = Decimal(str(tx.amount))
                if amt >= 0:
                    deposits += amt
                else:
                    withdrawals += abs(amt)

        totals = {
            'deposits': deposits,
            'withdrawals': withdrawals,
            'net': deposits - withdrawals,
        }
        pdf_bytes = build_agent_monthly_report_pdf(user, month_str, transactions, totals)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="releve_{month_str}.pdf"'
        return response


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def parse_vocal_mission(request):
    """
    [DEPRECATED V1] Pipeline vocal legacy — le client V1 joint l'audio brut
    à la création de mission. Conservé pour compatibilité ; ne pas utiliser
    dans les nouveaux parcours. Sera retiré en API v2.
    """
    from apps.missions.vocal_utils import (
        find_best_category,
        validate_extracted_json,
        geocode_address,
        compute_transcription_hash,
    )
    from apps.missions.models import VoiceMissionRequest

    if 'audio' not in request.FILES:
        return JsonResponse(
            {'error': 'Fichier audio requis'},
            status=status.HTTP_400_BAD_REQUEST
        )

    audio_file = request.FILES['audio']

    # ── Étape A0 : Hash audio pour anti-doublon upload ─────────────────────────
    import hashlib
    audio_hash = ''
    audio_chunks = []
    for chunk in audio_file.chunks():
        audio_chunks.append(chunk)
    audio_content = b''.join(audio_chunks)
    audio_hash = hashlib.sha256(audio_content).hexdigest()

    # ── Étape A : Transcription (Mistral Voxtral → Google STT) ───────────────
    import tempfile
    from django.conf import settings as django_settings
    from apps.missions.vocal_utils import transcribe_audio_file

    temp_path = None
    transcription = ''
    mistral_api_key = os.environ.get('MISTRAL_API_KEY') or getattr(
        django_settings, 'MISTRAL_API_KEY', None
    )
    try:
        suffix = os.path.splitext(audio_file.name or '')[1] or '.m4a'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
            for chunk in audio_chunks:
                tf.write(chunk)
            temp_path = tf.name

        transcription = transcribe_audio_file(
            temp_path,
            original_name=audio_file.name or f'audio{suffix}',
            mistral_api_key=mistral_api_key,
            language='fr',
        )

    except ValueError as e:
        err = str(e).lower()
        if 'incomprehensible' in err or 'unknown' in err:
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            message = 'Audio incompréhensible, veuillez parler plus clairement et réessayer'
        elif 'indisponible' in err or 'request' in err:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            message = f'Service de transcription indisponible: {e}'
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            message = f'Erreur transcription: {e}'
        VoiceMissionRequest.objects.create(
            user=request.user, audio_hash=audio_hash, status='error',
            transcription='', extracted_data={'error': message},
        )
        return JsonResponse({'error': message}, status=status_code)
    except Exception as e:
        return JsonResponse(
            {'error': f'Erreur transcription: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    # ── Étape B : Anti-doublon ───────────────────────────────────────────────
    t_hash = compute_transcription_hash(transcription)
    from django.utils import timezone as tz
    duplicate_window = tz.now() - timezone.timedelta(minutes=30)
    if VoiceMissionRequest.objects.filter(
        user=request.user,
        transcription_hash=t_hash,
        created_at__gte=duplicate_window,
        status__in=('complete', 'incomplete'),
    ).exists():
        return JsonResponse(
            {
                'error': 'Doublon détecté : une mission identique a été créée dans les 30 dernières minutes.',
                'code': 'duplicate',
            },
            status=status.HTTP_409_CONFLICT
        )

    # ── Étape C : Extraction IA ──────────────────────────────────────────────
    extracted_data: dict = {}
    missing_fields: list = []

    try:
        from mistralai import Mistral
        from django.conf import settings as django_settings
        mistral_api_key = os.environ.get('MISTRAL_API_KEY') or getattr(django_settings, 'MISTRAL_API_KEY', None)

        if mistral_api_key:
            mistral_client = Mistral(api_key=mistral_api_key)
            system_prompt = (
                "Tu es un assistant IA spécialisé dans l'extraction d'informations de missions de service. "
                "À partir d'une transcription textuelle, extrais UNIQUEMENT au format JSON :\n"
                '{"title":string|null,"description":string|null,"category":string|null,'
                '"budget":number|null,"scheduled_date":"ASAP"|"TODAY"|"TOMORROW"|"THIS_WEEK"|null,'
                '"scheduled_time_slot":"MORNING"|"AFTERNOON"|"EVENING"|null,'
                '"address":string|null,"is_urgent":boolean}\n'
                "Retourne UNIQUEMENT le JSON, sans texte supplémentaire."
            )
            response = mistral_client.chat.complete(
                model="mistral-large-latest",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": transcription},
                ],
            )
            raw_json = json.loads(response.choices[0].message.content)
        else:
            # Fallback sans IA : transcription brute
            raw_json = {
                'title': None, 'description': transcription,
                'category': None, 'budget': None,
                'scheduled_date': None, 'scheduled_time_slot': None,
                'address': None, 'is_urgent': False,
            }

        # ── Étape D : Validation schéma strict ──────────────────────────────
        cleaned, schema_errors = validate_extracted_json(raw_json)
        if schema_errors:
            VoiceMissionRequest.objects.create(
                user=request.user, audio_hash=audio_hash, transcription=transcription,
                transcription_hash=t_hash, status='error',
                extracted_data={'schema_errors': schema_errors},
            )
            return JsonResponse(
                {'error': 'Extraction IA invalide', 'details': schema_errors},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

        # ── Étape E : Mapping catégorie ──────────────────────────────────────
        category_obj = None
        category_id_resolved = None
        category_name_resolved = ''
        if cleaned.get('category'):
            category_obj = find_best_category(cleaned['category'])
            if category_obj:
                category_id_resolved = category_obj.id
                category_name_resolved = category_obj.name

        # ── Étape F : Géocodage adresse ──────────────────────────────────────
        lat, lng = None, None
        if cleaned.get('address'):
            lat, lng = geocode_address(cleaned['address'])
        # Fallback : utiliser GPS Flutter si géocodage échoue
        if lat is None or lng is None:
            lat = request.data.get('latitude')
            lng = request.data.get('longitude')
            if lat is not None and lng is not None:
                try:
                    lat = float(lat)
                    lng = float(lng)
                except (ValueError, TypeError):
                    lat, lng = None, None

        # ── Construire extracted_data SANS valeurs par défaut dangereuses ────
        extracted_data = {
            'title':               cleaned.get('title'),
            'description':         cleaned.get('description'),
            'category_id':         category_id_resolved,
            'category_name':       category_name_resolved or None,
            'budget':              cleaned.get('budget'),   # None = non mentionné
            'scheduled_date':      cleaned.get('scheduled_date'),
            'scheduled_time_slot': cleaned.get('scheduled_time_slot'),
            'address':             cleaned.get('address'),
            'latitude':            lat,   # None = non géocodé (Flutter demandera GPS)
            'longitude':           lng,
            'is_urgent':           cleaned.get('is_urgent', False),
        }

        # ── Étape G : Champs manquants → Flutter demande à l'utilisateur ────
        if not extracted_data['title']:
            missing_fields.append({
                'field': 'title',
                'question': 'Quel est l\'intitulé de votre mission ?',
                'ui_type': 'text_input',
            })
        if not extracted_data['category_id']:
            missing_fields.append({
                'field': 'category',
                'question': 'Quel type de service souhaitez-vous ?',
                'ui_type': 'category_picker',
            })
        if not extracted_data['scheduled_date']:
            missing_fields.append({
                'field': 'scheduled_date',
                'question': 'Quand l\'artisan doit-il intervenir ?',
                'ui_type': 'quick_buttons',
                'options': [
                    {'label': 'Urgent (Dès que possible) ⏱️', 'value': 'ASAP'},
                    {'label': 'Aujourd\'hui 📅', 'value': 'TODAY'},
                    {'label': 'Demain 🌅', 'value': 'TOMORROW'},
                    {'label': 'Cette semaine 🗓️', 'value': 'THIS_WEEK'},
                ],
            })
        if not extracted_data['scheduled_time_slot']:
            missing_fields.append({
                'field': 'scheduled_time_slot',
                'question': 'À quel moment préférez-vous ?',
                'ui_type': 'quick_buttons',
                'options': [
                    {'label': 'Matin (8h-12h) ☀️', 'value': 'MORNING'},
                    {'label': 'Après-midi (12h-17h) 🌤️', 'value': 'AFTERNOON'},
                    {'label': 'Soir (17h-21h) 🌙', 'value': 'EVENING'},
                ],
            })
        if not extracted_data['budget']:
            missing_fields.append({
                'field': 'budget',
                'question': 'Quel budget proposez-vous pour ce travail ?',
                'ui_type': 'price_suggestions',
                'options': [
                    {'label': 'Éco (5 000 FCFA)', 'value': 5000},
                    {'label': 'Standard (10 000 FCFA)', 'value': 10000},
                    {'label': 'Premium (18 000 FCFA)', 'value': 18000},
                    {'label': 'À négocier 💬', 'value': 0},
                ],
            })
        if not extracted_data['address']:
            missing_fields.append({
                'field': 'address',
                'question': 'À quelle adresse se déroule la mission ?',
                'ui_type': 'text_input',
            })

    except (ValueError, KeyError, json.JSONDecodeError) as e:
        VoiceMissionRequest.objects.create(
            user=request.user, audio_hash=audio_hash, transcription=transcription,
            transcription_hash=t_hash, status='error',
            extracted_data={'exception': str(e)},
        )
        return JsonResponse(
            {'error': f'Erreur extraction IA: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # ── Étape H : Audit VoiceMissionRequest ──────────────────────────────────
    final_status = 'incomplete' if missing_fields else 'complete'
    VoiceMissionRequest.objects.create(
        user=request.user,
        audio_hash=audio_hash,
        transcription=transcription,
        transcription_hash=t_hash,
        extracted_data=extracted_data,
        missing_fields=missing_fields,
        status=final_status,
        category_id_resolved=category_id_resolved,
        category_name_resolved=category_name_resolved,
    )

    return JsonResponse({
        'status': final_status,
        'transcription': transcription,
        'extracted_data': extracted_data,
        'missing_fields': missing_fields,
    }, status=status.HTTP_200_OK)
