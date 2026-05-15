from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import BoostPlan, AgentBoost
from .serializers import (
    BoostPlanSerializer, AgentBoostSerializer, 
    AgentBoostCreateSerializer, BoostCostCalculateSerializer
)


class BoostPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les plans de boost (lecture seule)"""
    queryset = BoostPlan.objects.filter(is_active=True)
    serializer_class = BoostPlanSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def calculate_cost(self, request):
        """Calculer le coût d'un boost"""
        serializer = BoostCostCalculateSerializer(data=request.data)
        if serializer.is_valid():
            plan = serializer.plan
            return Response({
                'plan_id': plan.id,
                'plan_name': plan.name,
                'duration_hours': plan.duration_hours,
                'duration_display': plan.duration_display,
                'price': plan.price,
                'visibility_multiplier': plan.visibility_multiplier
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AgentBoostViewSet(viewsets.ModelViewSet):
    """ViewSet pour les boosts d'agents"""
    serializer_class = AgentBoostSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Un agent ne voit que ses propres boosts
        if hasattr(self.request.user, 'agentprofile'):
            return AgentBoost.objects.filter(agent=self.request.user.agentprofile)
        return AgentBoost.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return AgentBoostCreateSerializer
        return AgentBoostSerializer
    
    def perform_create(self, serializer):
        # Associer le boost à l'agent connecté
        agent_profile = self.request.user.agentprofile
        serializer.save(agent=agent_profile)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Obtenir le boost actif de l'agent"""
        active_boost = self.get_queryset().filter(
            status='active'
        ).first()
        
        if active_boost:
            serializer = self.get_serializer(active_boost)
            return Response(serializer.data)
        
        return Response({
            'message': 'Aucun boost actif',
            'has_active_boost': False
        })
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """Historique complet des boosts de l'agent"""
        boosts = self.get_queryset().order_by('-started_at')
        serializer = self.get_serializer(boosts, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activer un boost (déjà actif par défaut)"""
        boost = self.get_object()
        
        if boost.status != 'active':
            boost.status = 'active'
            boost.save()
        
        serializer = self.get_serializer(boost)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Annuler un boost"""
        boost = self.get_object()
        
        if boost.status == 'active':
            boost.status = 'cancelled'
            boost.save()
            
            return Response({
                'message': 'Boost annulé avec succès',
                'status': boost.status
            })
        
        return Response({
            'message': 'Impossible d\'annuler ce boost',
            'reason': 'Le boost n\'est pas actif'
        }, status=status.HTTP_400_BAD_REQUEST)
