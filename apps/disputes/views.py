from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from .models import Dispute, DisputeEvidence, DisputeComment
from .serializers import (
    DisputeSerializer, DisputeCreateSerializer, DisputeResolveSerializer,
    DisputeEvidenceSerializer, DisputeEvidenceCreateSerializer,
    DisputeCommentSerializer
)


class IsOwnerOrStaff(permissions.BasePermission):
    """Permission pour vérifier si l'utilisateur est le propriétaire ou staff"""
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.opened_by == request.user


class DisputeViewSet(viewsets.ModelViewSet):
    """ViewSet pour les litiges"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Dispute.objects.all()
        return Dispute.objects.filter(
            Q(opened_by=user) | Q(mission__client=user) | Q(mission__agent=user)
        ).distinct()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return DisputeCreateSerializer
        elif self.action == 'resolve':
            return DisputeResolveSerializer
        return DisputeSerializer
    
    def perform_create(self, serializer):
        serializer.save(opened_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assigner un litige à un membre du staff (préparation super admin)."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN,
            )

        dispute = self.get_object()
        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {'error': 'user_id requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            staff_user = User.objects.get(pk=user_id, is_staff=True)
        except User.DoesNotExist:
            return Response(
                {'error': 'Membre staff introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )

        dispute.assigned_to = staff_user
        if dispute.status == 'open':
            dispute.status = 'under_review'
        dispute.save(update_fields=['assigned_to', 'status', 'updated_at'])
        return Response(
            DisputeSerializer(dispute, context={'request': request}).data,
        )

    @action(detail=True, methods=['post'])
    def escalate(self, request, pk=None):
        """Escalader un litige (préparation super admin)."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN,
            )

        dispute = self.get_object()
        priority = request.data.get('priority', 'high')
        if priority not in dict(Dispute.PRIORITY_CHOICES):
            return Response(
                {'error': 'Priorité invalide'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dispute.status = 'escalated'
        dispute.priority = priority
        dispute.save(update_fields=['status', 'priority', 'updated_at'])
        return Response(
            DisputeSerializer(dispute, context={'request': request}).data,
        )

    @action(detail=False, methods=['get'])
    def admin_queue(self, request):
        """File d'attente litiges ouverts (staff / super admin)."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN,
            )

        qs = Dispute.objects.filter(
            status__in=['open', 'under_review', 'escalated'],
        ).select_related('mission', 'opened_by', 'assigned_to').order_by('-priority', 'created_at')

        priority = request.query_params.get('priority')
        if priority:
            qs = qs.filter(priority=priority)

        serializer = self.get_serializer(qs, many=True)
        return Response({'results': serializer.data, 'count': qs.count()})

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Résoudre un litige (admin uniquement)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        dispute = self.get_object()
        serializer = self.get_serializer(dispute, data=request.data, partial=True)
        
        if serializer.is_valid():
            dispute = serializer.save(
                resolved_by=request.user,
                resolved_at=timezone.now(),
                status='resolved'
            )
            return Response(DisputeSerializer(dispute, context={'request': request}).data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def add_evidence(self, request, pk=None):
        """Ajouter une preuve à un litige"""
        dispute = self.get_object()
        
        # Vérifier les permissions
        if not (dispute.opened_by == request.user or request.user.is_staff):
            return Response(
                {'error': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = DisputeEvidenceCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            evidence = serializer.save(
                dispute=dispute,
                uploaded_by=request.user
            )
            return Response(
                DisputeEvidenceSerializer(evidence, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def evidences(self, request, pk=None):
        """Lister les preuves d'un litige"""
        dispute = self.get_object()
        evidences = dispute.evidences.all()
        serializer = DisputeEvidenceSerializer(evidences, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_comment(self, request, pk=None):
        """Ajouter un commentaire à un litige"""
        dispute = self.get_object()
        
        # Seul le staff peut ajouter des commentaires internes
        is_internal = request.data.get('is_internal', False)
        if is_internal and not request.user.is_staff:
            return Response(
                {'error': 'Permission refusée pour les commentaires internes'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        comment_data = {
            'dispute': dispute.id,
            'comment': request.data.get('comment'),
            'is_internal': is_internal
        }
        
        serializer = DisputeCommentSerializer(data=comment_data)
        if serializer.is_valid():
            comment = serializer.save(author=request.user)
            return Response(
                DisputeCommentSerializer(comment, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def comments(self, request, pk=None):
        """Lister les commentaires d'un litige"""
        dispute = self.get_object()
        user = request.user
        
        # Filtrer les commentaires selon le type d'utilisateur
        if user.is_staff:
            comments = dispute.comments.all()
        else:
            comments = dispute.comments.filter(is_internal=False)
        
        serializer = DisputeCommentSerializer(comments, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_disputes(self, request):
        """Lister les litiges de l'utilisateur connecté"""
        disputes = self.get_queryset()
        serializer = self.get_serializer(disputes, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques des litiges (admin uniquement)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        total_disputes = Dispute.objects.count()
        open_disputes = Dispute.objects.filter(status='open').count()
        resolved_disputes = Dispute.objects.filter(status='resolved').count()
        
        stats = {
            'total_disputes': total_disputes,
            'open_disputes': open_disputes,
            'resolved_disputes': resolved_disputes,
            'resolution_rate': (resolved_disputes / total_disputes * 100) if total_disputes > 0 else 0,
            'disputes_by_priority': {
                'low': Dispute.objects.filter(priority='low').count(),
                'medium': Dispute.objects.filter(priority='medium').count(),
                'high': Dispute.objects.filter(priority='high').count(),
                'critical': Dispute.objects.filter(priority='critical').count(),
            }
        }
        
        return Response(stats)


class DisputeEvidenceViewSet(viewsets.ModelViewSet):
    """ViewSet pour les preuves de litige"""
    serializer_class = DisputeEvidenceSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrStaff]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return DisputeEvidence.objects.all()
        return DisputeEvidence.objects.filter(uploaded_by=user)
