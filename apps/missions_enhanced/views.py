from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Count, Sum, Avg
from datetime import datetime, timedelta
from django.utils import timezone
from .models import MissionProof, MissionTimelineEvent, AgentStatistics
from .serializers import (
    MissionProofSerializer, MissionProofCreateSerializer,
    MissionTimelineEventSerializer, MissionTimelineEventCreateSerializer,
    AgentStatisticsSerializer, AgentDashboardStatsSerializer,
    MissionProofBulkCreateSerializer
)


class IsMissionParticipant(permissions.BasePermission):
    """Permission pour vérifier si l'utilisateur participe à la mission"""
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        return (obj.mission.client == user or 
                (hasattr(user, 'agentprofile') and obj.mission.assigned_agent == user.agentprofile))


class MissionProofViewSet(viewsets.ModelViewSet):
    """ViewSet pour les preuves de mission"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'agentprofile'):
            # Agent ne voit que les preuves de ses missions
            return MissionProof.objects.filter(
                mission__assigned_agent=user.agentprofile
            )
        else:
            # Client ne voit que les preuves de ses missions
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
            
            # Vérifier les permissions
            user = request.user
            if not hasattr(user, 'agentprofile'):
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
        if hasattr(user, 'agentprofile'):
            # Agent ne voit que les événements de ses missions
            return MissionTimelineEvent.objects.filter(
                mission__assigned_agent=user.agentprofile
            )
        else:
            # Client ne voit que les événements de ses missions
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
        # Vérifier les permissions
        try:
            from apps.missions.models import Mission
            mission = Mission.objects.get(id=mission_id)
            
            if not (mission.client == user or 
                   (hasattr(user, 'agentprofile') and mission.assigned_agent == user.agentprofile)):
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
        if hasattr(user, 'agentprofile'):
            return AgentStatistics.objects.filter(agent=user.agentprofile)
        return AgentStatistics.objects.none()
    
    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Statistiques du dashboard agent"""
        user = request.user
        if not hasattr(user, 'agentprofile'):
            return Response(
                {'error': 'Agent profile requis'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        agent = user.agentprofile
        
        # Calculer les stats
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        from apps.missions.models import Mission
        
        # Stats aujourd'hui
        today_missions = Mission.objects.filter(
            assigned_agent=agent,
            updated_at__date=today
        ).count()
        
        today_earnings = Mission.objects.filter(
            assigned_agent=agent,
            status='completed',
            updated_at__date=today
        ).aggregate(total=Sum('price'))['total'] or 0
        
        # Stats cette semaine
        week_missions = Mission.objects.filter(
            assigned_agent=agent,
            updated_at__date__gte=week_start
        ).count()
        
        week_earnings = Mission.objects.filter(
            assigned_agent=agent,
            status='completed',
            updated_at__date__gte=week_start
        ).aggregate(total=Sum('price'))['total'] or 0
        
        # Stats ce mois
        month_missions = Mission.objects.filter(
            assigned_agent=agent,
            updated_at__date__gte=month_start
        ).count()
        
        month_earnings = Mission.objects.filter(
            assigned_agent=agent,
            status='completed',
            updated_at__date__gte=month_start
        ).aggregate(total=Sum('price'))['total'] or 0
        
        # Stats globales
        total_missions = Mission.objects.filter(assigned_agent=agent).count()
        total_earnings = Mission.objects.filter(
            assigned_agent=agent,
            status='completed'
        ).aggregate(total=Sum('price'))['total'] or 0
        
        average_rating = agent.rating or 0
        completion_rate = (Mission.objects.filter(
            assigned_agent=agent,
            status='completed'
        ).count() / total_missions * 100) if total_missions > 0 else 0
        
        # Missions en cours
        active_missions = Mission.objects.filter(
            assigned_agent=agent,
            status__in=['accepted', 'agent_en_route', 'in_progress']
        ).count()
        
        pending_missions = Mission.objects.filter(
            assigned_agent=agent,
            status='pending'
        ).count()
        
        # Obtenir ou créer les stats détaillées
        stats, created = AgentStatistics.objects.get_or_create(agent=agent)
        
        dashboard_data = {
            'today_missions': today_missions,
            'today_earnings': today_earnings,
            'week_missions': week_missions,
            'week_earnings': week_earnings,
            'month_missions': month_missions,
            'month_earnings': month_earnings,
            'total_missions': total_missions,
            'total_earnings': total_earnings,
            'average_rating': average_rating,
            'completion_rate': completion_rate,
            'active_missions': active_missions,
            'pending_missions': pending_missions,
            'level': stats.level,
            'current_streak': stats.current_streak_days
        }
        
        serializer = AgentDashboardStatsSerializer(dashboard_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def update_stats(self, request):
        """Mettre à jour les statistiques (pour cron)"""
        user = request.user
        if not hasattr(user, 'agentprofile'):
            return Response(
                {'error': 'Agent profile requis'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        agent = user.agentprofile
        from apps.missions.models import Mission
        
        # Calculer les nouvelles stats
        total_missions = Mission.objects.filter(assigned_agent=agent).count()
        completed_missions = Mission.objects.filter(
            assigned_agent=agent,
            status='completed'
        ).count()
        cancelled_missions = Mission.objects.filter(
            assigned_agent=agent,
            status='cancelled'
        ).count()
        
        total_earnings = Mission.objects.filter(
            assigned_agent=agent,
            status='completed'
        ).aggregate(total=Sum('price'))['total'] or 0
        
        # Stats du mois
        month_start = timezone.now().date().replace(day=1)
        current_month_earnings = Mission.objects.filter(
            assigned_agent=agent,
            status='completed',
            updated_at__date__gte=month_start
        ).aggregate(total=Sum('price'))['total'] or 0
        
        # Mettre à jour ou créer les stats
        stats, created = AgentStatistics.objects.get_or_create(agent=agent)
        
        stats.total_missions = total_missions
        stats.completed_missions = completed_missions
        stats.cancelled_missions = cancelled_missions
        stats.total_earnings = total_earnings
        stats.current_month_earnings = current_month_earnings
        stats.average_rating = agent.rating or 0
        stats.completion_rate = (completed_missions / total_missions * 100) if total_missions > 0 else 0
        stats.save()
        
        return Response({
            'message': 'Statistiques mises à jour',
            'stats': AgentStatisticsSerializer(stats).data
        })
