from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, F
from django.utils import timezone
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D

from .models import Opportunity, OpportunityApplication, OpportunityMatch
from .serializers import (
    OpportunitySerializer, 
    OpportunityCreateSerializer,
    OpportunityListSerializer,
    OpportunityApplicationSerializer,
    OpportunityMatchSerializer
)
from .services import OpportunityMatchingService


class OpportunityViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des opportunités"""
    
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Retourne le serializer approprié selon l'action"""
        if self.action == 'create':
            return OpportunityCreateSerializer
        elif self.action == 'list':
            return OpportunityListSerializer
        return OpportunitySerializer
    
    def get_queryset(self):
        """Filtre les opportunités selon le rôle de l'utilisateur"""
        user = self.request.user
        
        if user.is_staff or user.is_superuser:
            # Admin : voit toutes les opportunités
            queryset = Opportunity.objects.all()
        else:
            # Client : voit ses opportunités
            queryset = Opportunity.objects.filter(client=user)
        
        # Filtres supplémentaires
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        type_filter = self.request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(type=type_filter)
        
        priority_filter = self.request.query_params.get('priority')
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)
        
        # Exclure les opportunités expirées
        queryset = queryset.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )
        
        return queryset.select_related('client', 'assigned_agent')
    
    def perform_create(self, serializer):
        """Crée une opportunité avec le client actuel"""
        serializer.save(client=self.request.user)
    
    @action(detail=True, methods=['POST'])
    def apply(self, request, pk=None):
        """Postuler à une opportunité"""
        opportunity = self.get_object()
        
        # Vérifier si l'utilisateur peut postuler
        if opportunity.client == request.user:
            return Response(
                {'error': 'Vous ne pouvez pas postuler à votre propre opportunité'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not opportunity.can_be_assigned:
            return Response(
                {'error': 'Cette opportunité n\'est plus disponible'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Vérifier si déjà postulé
        if OpportunityApplication.objects.filter(
            opportunity=opportunity, 
            agent=request.user
        ).exists():
            return Response(
                {'error': 'Vous avez déjà postulé à cette opportunité'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Créer la candidature
        application = OpportunityApplication.objects.create(
            opportunity=opportunity,
            agent=request.user,
            message=request.data.get('message', ''),
            proposed_price=request.data.get('proposed_price')
        )
        
        serializer = OpportunityApplicationSerializer(application)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['GET'])
    def applications(self, request, pk=None):
        """Liste des candidatures pour une opportunité (propriétaire uniquement)"""
        opportunity = self.get_object()
        
        if opportunity.client != request.user:
            return Response(
                {'error': 'Accès non autorisé'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        applications = opportunity.applications.select_related('agent').order_by('-created_at')
        serializer = OpportunityApplicationSerializer(applications, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['POST'])
    def assign_agent(self, request, pk=None):
        """Assigner un agent à une opportunité (propriétaire uniquement)"""
        opportunity = self.get_object()
        
        if opportunity.client != request.user:
            return Response(
                {'error': 'Accès non autorisé'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        agent_id = request.data.get('agent_id')
        if not agent_id:
            return Response(
                {'error': 'ID de l\'agent requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            agent = User.objects.get(id=agent_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Agent non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Assigner l'agent
        opportunity.assigned_agent = agent
        opportunity.status = 'completed'
        opportunity.save()
        
        # Accepter la candidature correspondante
        OpportunityApplication.objects.filter(
            opportunity=opportunity,
            agent=agent
        ).update(status='accepted')
        
        # Refuser les autres candidatures
        OpportunityApplication.objects.filter(
            opportunity=opportunity
        ).exclude(agent=agent).update(status='rejected')
        
        serializer = self.get_serializer(opportunity)
        return Response(serializer.data)
    
    @action(detail=False, methods=['GET'])
    def nearby(self, request):
        """Opportunités près de la position de l'agent"""
        if not request.user.is_agent:
            return Response(
                {'error': 'Réservé aux agents'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Récupérer la position de l'agent
        lat = request.query_params.get('latitude')
        lng = request.query_params.get('longitude')
        
        if not lat or not lng:
            return Response(
                {'error': 'Latitude et longitude requises'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user_location = Point(float(lng), float(lat), srid=4326)
            max_distance = float(request.query_params.get('radius', 10))  # km par défaut
        except (ValueError, TypeError):
            return Response(
                {'error': 'Coordonnées invalides'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Rechercher les opportunités nearby
        opportunities = Opportunity.objects.filter(
            status='active',
            assigned_agent__isnull=True,
            pickup_latitude__isnull=False,
            pickup_longitude__isnull=False
        ).annotate(
            distance=Distance(
                'pickup_location',
                user_location
            )
        ).filter(
            distance__lte=D(km=max_distance)
        ).order_by('distance')
        
        serializer = OpportunityListSerializer(opportunities, many=True)
        return Response(serializer.data)


class OpportunityApplicationViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des candidatures"""
    
    permission_classes = [IsAuthenticated]
    serializer_class = OpportunityApplicationSerializer
    
    def get_queryset(self):
        """Filtre les candidatures selon l'utilisateur"""
        user = self.request.user
        
        if user.is_staff or user.is_superuser:
            return OpportunityApplication.objects.all()
        elif user.is_agent:
            return OpportunityApplication.objects.filter(agent=user)
        else:
            return OpportunityApplication.objects.filter(opportunity__client=user)
    
    @action(detail=True, methods=['POST'])
    def accept(self, request, pk=None):
        """Accepter une candidature (propriétaire de l'opportunité uniquement)"""
        application = self.get_object()
        
        if application.opportunity.client != request.user:
            return Response(
                {'error': 'Accès non autorisé'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Accepter la candidature
        application.status = 'accepted'
        application.save()
        
        # Assigner l'agent à l'opportunité
        opportunity = application.opportunity
        opportunity.assigned_agent = application.agent
        opportunity.status = 'completed'
        opportunity.save()
        
        # Refuser les autres candidatures
        OpportunityApplication.objects.filter(
            opportunity=opportunity
        ).exclude(id=application.id).update(status='rejected')
        
        serializer = self.get_serializer(application)
        return Response(serializer.data)
    
    @action(detail=True, methods=['POST'])
    def reject(self, request, pk=None):
        """Refuser une candidature (propriétaire de l'opportunité uniquement)"""
        application = self.get_object()
        
        if application.opportunity.client != request.user:
            return Response(
                {'error': 'Accès non autorisé'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        application.status = 'rejected'
        application.save()
        
        serializer = self.get_serializer(application)
        return Response(serializer.data)


class OpportunityMatchViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les matchs d'opportunités (lecture seule)"""
    
    permission_classes = [IsAuthenticated]
    serializer_class = OpportunityMatchSerializer
    
    def get_queryset(self):
        """Retourne les matchs pour l'utilisateur actuel"""
        if self.request.user.is_agent:
            return OpportunityMatch.objects.filter(agent=self.request.user)
        else:
            return OpportunityMatch.objects.filter(opportunity__client=self.request.user)
    
    @action(detail=False, methods=['GET'])
    def my_matches(self, request):
        """Matchs pour l'agent connecté"""
        if not request.user.is_agent:
            return Response(
                {'error': 'Réservé aux agents'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Récupérer la position actuelle de l'agent
        matching_service = OpportunityMatchingService()
        matches = matching_service.find_matches_for_agent(request.user)
        
        serializer = self.get_serializer(matches, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['POST'])
    def refresh_matches(self, request):
        """Rafraîchir les matchs pour l'agent connecté"""
        if not request.user.is_agent:
            return Response(
                {'error': 'Réservé aux agents'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        matching_service = OpportunityMatchingService()
        matches = matching_service.update_matches_for_agent(request.user)
        
        serializer = self.get_serializer(matches, many=True)
        return Response(serializer.data)
