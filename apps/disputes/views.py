from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.core.admin_audit import log_admin_action

from .models import Dispute
from .resolution import DisputeResolutionService
from .serializers import (
  DisputeCreateSerializer,
  DisputeResolveSerializer,
  DisputeSerializer,
)


class DisputeViewSet(viewsets.ModelViewSet):
  """API litiges — création client/agent, résolution SuperAdmin."""

  authentication_classes = [SessionAuthentication, JWTAuthentication]
  permission_classes = [permissions.IsAuthenticated]
  http_method_names = ['get', 'post', 'head', 'options']

  def get_queryset(self):
    user = self.request.user
    if getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False):
      return Dispute.objects.select_related(
        'mission', 'opened_by', 'assigned_to', 'resolved_by',
      ).order_by('-created_at')
    return Dispute.objects.filter(
      Q(mission__client=user) | Q(mission__agent=user),
    ).select_related(
      'mission', 'opened_by', 'assigned_to', 'resolved_by',
    ).order_by('-created_at')

  def get_serializer_class(self):
    if self.action == 'create':
      return DisputeCreateSerializer
    if self.action == 'resolve':
      return DisputeResolveSerializer
    return DisputeSerializer

  def create(self, request, *args, **kwargs):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    dispute = serializer.save()
    return Response(
      DisputeSerializer(dispute, context={'request': request}).data,
      status=status.HTTP_201_CREATED,
    )

  @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
  def resolve(self, request, pk=None):
    """Arbitrage SuperAdmin : REFUND_CLIENT | PAY_AGENT | ARBITRAGE_SPLIT."""
    dispute = get_object_or_404(Dispute, pk=pk)
    serializer = DisputeResolveSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
      DisputeResolutionService.resolve(
        dispute,
        data['resolution_type'],
        admin_user=request.user,
        notes=data.get('notes', ''),
        client_percent=data.get('client_percent'),
        agent_percent=data.get('agent_percent'),
      )
    except ValueError as exc:
      return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    log_admin_action(
      request.user,
      'DISPUTE_RESOLVE',
      target_type='Dispute',
      target_id=pk,
      detail=data['resolution_type'],
      metadata={'notes': data.get('notes', '')},
    )

    dispute.refresh_from_db()
    return Response(
      DisputeSerializer(dispute, context={'request': request}).data,
    )
