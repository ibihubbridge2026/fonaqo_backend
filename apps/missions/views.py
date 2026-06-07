from rest_framework import viewsets, permissions, status, pagination
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Count, Sum, Avg
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
from .models import Mission, MissionProof, MissionTimelineEvent, AgentStatistics
from .serializers import (
    MissionProofSerializer, MissionProofCreateSerializer,
    MissionTimelineEventSerializer, MissionTimelineEventCreateSerializer,
    AgentStatisticsSerializer, AgentDashboardStatsSerializer,
    MissionProofBulkCreateSerializer, MissionDetailSerializer, MissionCreateSerializer,
)
from apps.wallets.models import Wallet, Transaction
from apps.escrow.models import Escrow
from apps.core.choices import TransactionStatus, EscrowStatus


class MissionPagination(pagination.PageNumberPagination):
    """Pagination personnalisée pour les missions (20 par page)"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

_STATUS_EVENT_MAP = {
    'ON_THE_WAY': 'agent_en_route',
    'ARRIVED': 'agent_arrived',
    'IN_PROGRESS': 'in_progress',
    'COMPLETED': 'completed',
    'CANCELLED': 'cancelled',
    'ACCEPTED': 'accepted',
    'PENDING': 'created',
    'DISPUTED': 'disputed',
}


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

    def _lock_funds_in_escrow(self, mission):
        """Bloque les fonds du client en escrow lors de l'acceptation/démarrage"""
        with transaction.atomic():
            client_wallet, _ = Wallet.objects.get_or_create(user=mission.client)
            client_wallet = Wallet.objects.select_for_update().get(pk=client_wallet.pk)
            total_amount = mission.price + mission.service_fee

            if client_wallet.balance < total_amount:
                raise ValueError("Solde client insuffisant pour bloquer les fonds")

            # Déduire du solde du client
            client_wallet.balance -= total_amount
            client_wallet.escrow_balance += total_amount
            client_wallet.save()

            # Créer ou mettre à jour l'escrow
            escrow, created = Escrow.objects.get_or_create(
                mission=mission,
                defaults={'amount': total_amount, 'status': EscrowStatus.HELD}
            )
            if not created:
                escrow.amount = total_amount
                escrow.status = EscrowStatus.HELD
                escrow.save()

            # Enregistrer la transaction
            Transaction.objects.create(
                wallet=client_wallet,
                amount=total_amount,
                transaction_type=Transaction.TransactionType.ESCROW_LOCK,
                status=TransactionStatus.COMPLETED,
                description=f"Séquestre pour mission {mission.id}"
            )

    def _release_funds_from_escrow(self, mission):
        """Libère les fonds de l'escrow vers le wallet de l'agent"""
        if not mission.agent:
            raise ValueError("Aucun agent assigné à cette mission")

        client_wallet, _ = Wallet.objects.get_or_create(user=mission.client)
        agent_wallet, _ = Wallet.objects.get_or_create(user=mission.agent)

        try:
            escrow = Escrow.objects.get(mission=mission)
        except Escrow.DoesNotExist:
            raise ValueError("Aucun escrow trouvé pour cette mission")

        with transaction.atomic():
            client_wallet = Wallet.objects.select_for_update().get(pk=client_wallet.pk)
            agent_wallet = Wallet.objects.select_for_update().get(pk=agent_wallet.pk)

            # Libérer du séquestre du client
            client_wallet.escrow_balance -= escrow.amount
            client_wallet.save()

            # Ajouter au wallet de l'agent
            agent_wallet.balance += escrow.amount
            agent_wallet.save()

            # Mettre à jour l'escrow
            escrow.status = EscrowStatus.RELEASED
            escrow.released_at = timezone.now()
            escrow.save()

            # Enregistrer la transaction pour l'agent
            Transaction.objects.create(
                wallet=agent_wallet,
                amount=escrow.amount,
                transaction_type=Transaction.TransactionType.ESCROW_RELEASE,
                status=TransactionStatus.COMPLETED,
                description=f"Libération séquestre mission {mission.id}"
            )

    def _release_purchase_to_agent(self, mission):
        """Transfère immédiatement le montant des achats du client vers l'agent.

        Déclenché à l'acceptation de la mission : contrairement aux frais de
        prestation (séquestre), le montant des achats est débloqué tout de suite
        pour que l'agent puisse avancer les frais réels (courses, taxes, etc.).
        """
        if not mission.agent:
            raise ValueError("Aucun agent assigné à cette mission")

        if mission.purchase_released or mission.purchase_amount <= 0:
            return

        client_wallet, _ = Wallet.objects.get_or_create(user=mission.client)
        agent_wallet, _ = Wallet.objects.get_or_create(user=mission.agent)

        amount = mission.purchase_amount
        if client_wallet.balance < amount:
            raise ValueError("Solde client insuffisant pour débloquer les achats")

        with transaction.atomic():
            # Débit immédiat du client
            client_wallet.balance -= amount
            client_wallet.save(update_fields=["balance", "updated_at"])

            # Crédit immédiat de l'agent
            agent_wallet.balance += amount
            agent_wallet.save(update_fields=["balance", "updated_at"])

            # Marquer comme transféré pour éviter un double déblocage
            mission.purchase_released = True
            mission.save(update_fields=["purchase_released", "updated_at"])

            # Logs de transaction
            Transaction.objects.create(
                wallet=client_wallet,
                mission=mission,
                amount=-amount,
                transaction_type=Transaction.TransactionType.TRANSFER,
                status=TransactionStatus.COMPLETED,
                description=f"Déblocage achats mission {mission.id}",
            )
            Transaction.objects.create(
                wallet=agent_wallet,
                mission=mission,
                amount=amount,
                transaction_type=Transaction.TransactionType.TRANSFER,
                status=TransactionStatus.COMPLETED,
                description=f"Avance achats reçue mission {mission.id}",
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
            serializer = MissionDetailSerializer(page, many=True)
            return Response({
                'status': 'success',
                'message': 'Missions récupérées',
                'data': paginator.get_paginated_response(serializer.data).data
            })
        
        serializer = MissionDetailSerializer(qs, many=True)
        return Response({
            'status': 'success',
            'message': 'Missions récupérées',
            'data': {'results': serializer.data}
        })

    def retrieve(self, request, pk=None):
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        return Response(MissionDetailSerializer(mission).data)

    def create(self, request):
        serializer = MissionCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            mission = serializer.save()
            self._log_event(mission, 'created', request.user)
            return Response(MissionDetailSerializer(mission).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # ------------------------------------------------------------------
    # Custom list actions
    # ------------------------------------------------------------------

    @action(detail=False, methods=['get'])
    def available(self, request):
        """Missions PENDING sans agent assigné (pour les agents)."""
        qs = Mission.objects.filter(status='PENDING', agent__isnull=True).order_by('-created_at')
        
        # Apply pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            serializer = MissionDetailSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = MissionDetailSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def history(self, request):
        """Historique des missions complètes/annulées de l'agent."""
        limit = int(request.query_params.get('limit', 20))
        qs = Mission.objects.filter(
            agent=request.user,
            status__in=['COMPLETED', 'CANCELLED'],
        ).order_by('-updated_at')[:limit]
        return Response({'results': MissionDetailSerializer(qs, many=True).data})

    # ------------------------------------------------------------------
    # Custom detail actions
    # ------------------------------------------------------------------

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        mission = get_object_or_404(Mission, pk=pk)
        if mission.status != 'PENDING':
            return Response(
                {'status': 'error', 'message': 'Mission non disponible'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            # Bloquer les fonds en escrow
            self._lock_funds_in_escrow(mission)
        except ValueError as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            with transaction.atomic():
                mission.agent = request.user
                mission.status = 'ACCEPTED'
                mission.save()
                # Déblocage immédiat du montant des achats vers l'agent (hors séquestre)
                self._release_purchase_to_agent(mission)
        except ValueError as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        self._log_event(mission, 'accepted', request.user)
        return Response(MissionDetailSerializer(mission).data)

    @action(detail=True, methods=['post'])
    def start_mission(self, request, pk=None):
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        if mission.agent != request.user:
            return Response({'status': 'error', 'message': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)
        mission.status = 'IN_PROGRESS'
        mission.save()
        self._log_event(mission, 'in_progress', request.user)
        return Response(MissionDetailSerializer(mission).data)

    @action(detail=True, methods=['post'])
    def mark_completed_live(self, request, pk=None):
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        if mission.agent != request.user:
            return Response({'status': 'error', 'message': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)
        mission.status = 'COMPLETED'
        mission.save()
        self._log_event(mission, 'completed', request.user)
        return Response(MissionDetailSerializer(mission).data)

    @action(detail=True, methods=['post'])
    def update_steps(self, request, pk=None):
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        _AGENT_ALLOWED_STEPS = {'ON_THE_WAY', 'ARRIVED'}
        new_status = request.data.get('status')
        if not new_status or new_status not in _AGENT_ALLOWED_STEPS:
            return Response(
                {'status': 'error', 'message': f'Statut invalide. Valeurs acceptées : {", ".join(_AGENT_ALLOWED_STEPS)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        mission.status = new_status
        mission.save(update_fields=['status', 'updated_at'])
        self._log_event(mission, _STATUS_EVENT_MAP[new_status], request.user, request.data)
        return Response(MissionDetailSerializer(mission).data)

    @action(detail=True, methods=['post'])
    def submit_completion(self, request, pk=None):
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        if mission.agent != request.user:
            return Response({'status': 'error', 'message': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)
        if 'photo' in request.FILES:
            mission.end_photo = request.FILES['photo']
        mission.status = 'COMPLETED'
        mission.save()
        self._log_event(mission, 'proofs_uploaded', request.user)
        return Response(MissionDetailSerializer(mission).data)

    @action(detail=True, methods=['post'])
    def validate_completion(self, request, pk=None):
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        qr_data = request.data.get('qr_code_data', '')
        if mission.qr_code_token != qr_data:
            return Response({'status': 'error', 'message': 'QR Code invalide'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Libérer les fonds de l'escrow vers l'agent
            self._release_funds_from_escrow(mission)
        except ValueError as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        mission.qr_code_token = uuid.uuid4().hex
        mission.save(update_fields=['qr_code_token'])
        self._log_event(mission, 'validated', request.user)
        return Response({'status': 'success', 'message': 'Mission validée et fonds libérés'})

    @action(detail=True, methods=['post'])
    def open_dispute(self, request, pk=None):
        mission, err = self._get_mission(pk, request.user)
        if err:
            return err
        reason = request.data.get('reason', '')
        description = request.data.get('description', '')
        mission.status = 'DISPUTED'
        mission.save()
        self._log_event(mission, 'disputed', request.user, {'notes': f'{reason}: {description}'})
        return Response({'status': 'success', 'message': 'Litige ouvert'})

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
        mission.save()
        
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
        
        if mission.status not in ['IN_PROGRESS', 'ON_THE_WAY', 'ARRIVED']:
            return Response(
                {'status': 'error', 'message': 'La mission doit être en cours pour être validée'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Libérer les fonds de l'escrow vers l'agent
            self._release_funds_from_escrow(mission)
        except ValueError as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        mission.status = 'COMPLETED'
        mission.save()
        self._log_event(mission, 'validated_remotely', request.user)
        
        return Response({
            'status': 'success',
            'message': 'Mission validée manuellement et fonds libérés'
        })

    @action(detail=False, methods=['get'])
    def monthly_report(self, request):
        """Génère un relevé mensuel d'activité pour l'agent connecté"""
        if not request.user.is_agent:
            return Response(
                {'status': 'error', 'message': 'Réservé aux agents'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Récupérer le mois depuis les query params (format: YYYY-MM)
        month_str = request.query_params.get('month')
        if not month_str:
            month_str = timezone.now().strftime('%Y-%m')
        
        try:
            year, month = map(int, month_str.split('-'))
            start_date = timezone.datetime(year, month, 1).replace(tzinfo=timezone.utc)
            if month == 12:
                end_date = timezone.datetime(year + 1, 1, 1).replace(tzinfo=timezone.utc)
            else:
                end_date = timezone.datetime(year, month + 1, 1).replace(tzinfo=timezone.utc)
        except (ValueError, IndexError):
            return Response(
                {'status': 'error', 'message': 'Format de mois invalide (YYYY-MM)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Récupérer les missions de l'agent pour le mois
        missions = Mission.objects.filter(
            agent=request.user,
            created_at__gte=start_date,
            created_at__lt=end_date
        ).order_by('-created_at')
        
        # Calculer les statistiques
        total_missions = missions.count()
        completed_missions = missions.filter(status='COMPLETED').count()
        cancelled_missions = missions.filter(status='CANCELLED').count()
        total_earnings = missions.filter(status='COMPLETED').aggregate(total=Sum('price'))['total'] or 0
        
        # Créer le PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="releve_{month_str}.pdf"'
        
        doc = SimpleDocTemplate(response, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        # Titre
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#FFD400'),
            spaceAfter=30
        )
        elements.append(Paragraph(f"Relevé d'Activité - {month_str}", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Info agent
        agent_info = f"Agent: {request.user.username} | Tel: {request.user.phone_number}"
        elements.append(Paragraph(agent_info, styles['Normal']))
        elements.append(Spacer(1, 0.3*inch))
        
        # Statistiques
        stats_data = [
            ['Statistique', 'Valeur'],
            ['Total Missions', str(total_missions)],
            ['Missions Complétées', str(completed_missions)],
            ['Missions Annulées', str(cancelled_missions)],
            ['Gains Totaux', f"{total_earnings:.2f} FCFA"]
        ]
        
        stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFD400')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(stats_table)
        elements.append(Spacer(1, 0.5*inch))
        
        # Détail des missions
        elements.append(Paragraph("Détail des Missions", styles['Heading2']))
        elements.append(Spacer(1, 0.2*inch))
        
        mission_data = [['Date', 'Titre', 'Statut', 'Montant']]
        for mission in missions[:50]:  # Limiter à 50 missions
            mission_data.append([
                mission.created_at.strftime('%d/%m/%Y'),
                mission.title[:30],
                mission.status,
                f"{mission.price:.2f} FCFA"
            ])
        
        mission_table = Table(mission_data, colWidths=[1*inch, 2.5*inch, 1.5*inch, 1.5*inch])
        mission_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFD400')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 9)
        ]))
        elements.append(mission_table)
        
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
                When(status__in=['ACCEPTED', 'ON_THE_WAY', 'IN_PROGRESS', 'ARRIVED'], then=1),
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


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def parse_vocal_mission(request):
    """
    Endpoint pour parser un fichier audio vocal et extraire les informations de mission.
    Pipeline: Audio -> Transcription (SpeechRecognition/Google STT) -> Extraction JSON (Mistral AI)
    """
    if 'audio' not in request.FILES:
        return JsonResponse(
            {'error': 'Fichier audio requis'},
            status=status.HTTP_400_BAD_REQUEST
        )

    audio_file = request.FILES['audio']

    # Étape A: Transcription avec SpeechRecognition (Google STT, sans clé OpenAI)
    import tempfile
    import speech_recognition as sr
    from pydub import AudioSegment

    temp_path = None
    wav_path = None
    try:
        suffix = os.path.splitext(audio_file.name or '')[1] or '.m4a'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            for chunk in audio_file.chunks():
                temp_file.write(chunk)
            temp_path = temp_file.name

        # Convertir en WAV (pydub gère m4a, mp3, ogg, etc. via ffmpeg)
        audio_segment = AudioSegment.from_file(temp_path)
        wav_path = temp_path.rsplit('.', 1)[0] + '.wav'
        audio_segment.export(wav_path, format='wav')

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            transcription = recognizer.recognize_google(audio_data, language='fr-FR')

    except sr.UnknownValueError:
        return JsonResponse(
            {'error': 'Audio incompréhensible, veuillez parler plus clairement et réessayer'},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
    except sr.RequestError as e:
        return JsonResponse(
            {'error': f'Service de transcription indisponible: {str(e)}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except Exception as e:
        return JsonResponse(
            {'error': f'Erreur transcription: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    finally:
        for p in [temp_path, wav_path]:
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except OSError:
                    pass

    # Étape B: Extraction JSON avec Mistral AI (SDK officiel)
    try:
        from mistralai import Mistral
        from django.conf import settings as django_settings
        mistral_api_key = os.environ.get('MISTRAL_API_KEY') or getattr(django_settings, 'MISTRAL_API_KEY', None)

        if not mistral_api_key:
            # Fallback: extraction basique sans IA
            extracted_data = {
                'title': 'Mission vocale',
                'description': transcription,
                'category_id': None,
                'budget': None,
                'scheduled_date': None,
                'scheduled_time_slot': None,
                'address': None,
                'latitude': None,
                'longitude': None,
            }
            missing_fields = [
                {
                    'field': 'scheduled_date',
                    'question': 'Quand l\'artisan doit-il intervenir ?',
                    'ui_type': 'quick_buttons',
                    'options': [
                        {'label': 'Urgent (Dès que possible) ⏱️', 'value': 'ASAP'},
                        {'label': 'Aujourd\'hui 📅', 'value': 'TODAY'},
                        {'label': 'Demain 🌅', 'value': 'TOMORROW'},
                        {'label': 'Cette semaine 🗓️', 'value': 'THIS_WEEK'}
                    ]
                },
                {
                    'field': 'budget',
                    'question': 'Quel budget proposez-vous pour ce travail ?',
                    'ui_type': 'price_suggestions',
                    'options': [
                        {'label': 'Éco (5 000 FCFA)', 'value': 5000},
                        {'label': 'Standard (10 000 FCFA)', 'value': 10000},
                        {'label': 'Premium (18 000 FCFA)', 'value': 18000},
                        {'label': 'À négocier 💬', 'value': 0}
                    ]
                }
            ]
        else:
            # Utiliser Mistral AI via SDK officiel
            mistral_client = Mistral(api_key=mistral_api_key)

            system_prompt = """Tu es un assistant IA spécialisé dans l'extraction d'informations de missions de service.
À partir d'une transcription textuelle, extrais les informations suivantes au format JSON strict:
{
  "title": "Titre court de la mission",
  "description": "Description détaillée",
  "category": "Catégorie du service (plomberie, électricité, ménage, etc.)",
  "budget": "Montant estimé en FCFA (null si non mentionné)",
  "scheduled_date": "Date souhaitée (ASAP, TODAY, TOMORROW, THIS_WEEK, null si non mentionné)",
  "scheduled_time_slot": "Créneau horaire (MORNING, AFTERNOON, EVENING, null si non mentionné)",
  "address": "Adresse ou localisation (null si non mentionné)",
  "is_urgent": "true si urgent, false sinon"
}

Retourne UNIQUEMENT le JSON, sans texte supplémentaire."""

            response = mistral_client.chat.complete(
                model="mistral-large-latest",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": transcription}
                ],
            )

            extracted_json = json.loads(response.choices[0].message.content)
            
            # Mapper les champs extraits
            extracted_data = {
                'title': extracted_json.get('title'),
                'description': extracted_json.get('description'),
                'category_id': None,  # À mapper avec les catégories existantes
                'budget': extracted_json.get('budget'),
                'scheduled_date': extracted_json.get('scheduled_date'),
                'scheduled_time_slot': extracted_json.get('scheduled_time_slot'),
                'address': extracted_json.get('address'),
                'latitude': None,
                'longitude': None,
            }

            # Générer les champs manquants
            missing_fields = []
            
            if not extracted_data.get('scheduled_date'):
                missing_fields.append({
                    'field': 'scheduled_date',
                    'question': 'Quand l\'artisan doit-il intervenir ?',
                    'ui_type': 'quick_buttons',
                    'options': [
                        {'label': 'Urgent (Dès que possible) ⏱️', 'value': 'ASAP'},
                        {'label': 'Aujourd\'hui 📅', 'value': 'TODAY'},
                        {'label': 'Demain 🌅', 'value': 'TOMORROW'},
                        {'label': 'Cette semaine 🗓️', 'value': 'THIS_WEEK'}
                    ]
                })
            
            if not extracted_data.get('scheduled_time_slot'):
                missing_fields.append({
                    'field': 'scheduled_time_slot',
                    'question': 'À quel moment préférez-vous ?',
                    'ui_type': 'quick_buttons',
                    'options': [
                        {'label': 'Matin (8h-12h) ☀️', 'value': 'MORNING'},
                        {'label': 'Après-midi (12h-17h) 🌤️', 'value': 'AFTERNOON'},
                        {'label': 'Soir (17h-21h) 🌙', 'value': 'EVENING'}
                    ]
                })
            
            if not extracted_data.get('budget'):
                missing_fields.append({
                    'field': 'budget',
                    'question': 'Quel budget proposez-vous pour ce travail ?',
                    'ui_type': 'price_suggestions',
                    'options': [
                        {'label': 'Éco (5 000 FCFA)', 'value': 5000},
                        {'label': 'Standard (10 000 FCFA)', 'value': 10000},
                        {'label': 'Premium (18 000 FCFA)', 'value': 18000},
                        {'label': 'À négocier 💬', 'value': 0}
                    ]
                })

    except Exception as e:
        return JsonResponse(
            {'error': f'Erreur extraction IA: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Étape C: Construire la réponse
    response_data = {
        'status': 'incomplete' if missing_fields else 'complete',
        'transcription': transcription,
        'extracted_data': extracted_data,
        'missing_fields': missing_fields
    }

    return JsonResponse(response_data, status=status.HTTP_200_OK)
