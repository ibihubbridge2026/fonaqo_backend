from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import BoostPlan, AgentBoost
from .serializers import (
    BoostPlanSerializer, AgentBoostSerializer,
    AgentBoostCreateSerializer, BoostCostCalculateSerializer,
)


class BoostPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les plans de boost (lecture seule)"""
    queryset = BoostPlan.objects.filter(is_active=True)
    serializer_class = BoostPlanSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'])
    def calculate_cost(self, request):
        serializer = BoostCostCalculateSerializer(data=request.data)
        if serializer.is_valid():
            plan = serializer.plan
            return Response({
                'plan_id': plan.id,
                'plan_name': plan.name,
                'duration_hours': plan.duration_hours,
                'duration_display': plan.duration_display,
                'price': plan.price,
                'visibility_multiplier': plan.visibility_multiplier,
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AgentBoostViewSet(viewsets.ModelViewSet):
    """ViewSet pour les boosts d'agents."""
    serializer_class = AgentBoostSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_agent:
            return AgentBoost.objects.filter(agent=user)
        return AgentBoost.objects.none()

    def get_serializer_class(self):
        if self.action == 'create':
            return AgentBoostCreateSerializer
        return AgentBoostSerializer

    def perform_create(self, serializer):
        serializer.save(agent=self.request.user)

    @action(detail=False, methods=['get'])
    def active(self, request):
        now = timezone.now()
        active_boost = self.get_queryset().filter(
            status='active',
            expires_at__gt=now,
        ).first()

        if active_boost:
            return Response(self.get_serializer(active_boost).data)

        return Response({
            'message': 'Aucun boost actif',
            'has_active_boost': False,
        })

    @action(detail=False, methods=['post'], url_path='purchase')
    def purchase(self, request):
        """Achat boost via solde portefeuille ou FeexPay (transaction_id)."""
        user = request.user
        if not user.is_agent:
            return Response({'message': 'Réservé aux agents'}, status=status.HTTP_403_FORBIDDEN)

        plan_id = request.data.get('plan_id') or request.data.get('boost_type')
        payment_method = request.data.get('payment_method', 'wallet')
        transaction_id = request.data.get('transaction_id', '')

        try:
            if isinstance(plan_id, int) or (isinstance(plan_id, str) and plan_id.isdigit()):
                plan = BoostPlan.objects.get(pk=int(plan_id), is_active=True)
            else:
                plan = BoostPlan.objects.get(name__iexact=str(plan_id), is_active=True)
        except BoostPlan.DoesNotExist:
            return Response({'message': 'Plan de boost invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        amount = Decimal(str(plan.price))

        with transaction.atomic():
            if payment_method == 'wallet':
                from apps.wallets.models import Wallet, Transaction as WalletTransaction

                wallet = Wallet.objects.select_for_update().get(user=user)
                if wallet.balance < amount:
                    return Response(
                        {'message': 'Solde insuffisant.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                wallet.balance -= amount
                wallet.save(update_fields=['balance', 'updated_at'])
                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=-amount,
                    transaction_type=WalletTransaction.TransactionType.BOOST_PAYMENT,
                    description=f'Achat boost {plan.name}',
                    status='COMPLETED',
                )
                transaction_id = transaction_id or f'WALLET-{int(timezone.now().timestamp())}'
            elif payment_method == 'feexpay':
                if not transaction_id:
                    return Response(
                        {'message': 'transaction_id FeexPay requis.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    {'message': 'Mode de paiement invalide.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            expires_at = timezone.now() + timedelta(hours=plan.duration_hours)
            boost = AgentBoost.objects.create(
                agent=user,
                plan=plan,
                expires_at=expires_at,
                status='active',
                purchase_amount=amount,
                transaction_id=transaction_id or f'FEEX-{int(timezone.now().timestamp())}',
            )

        return Response(
            AgentBoostSerializer(boost).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'])
    def history(self, request):
        boosts = self.get_queryset().order_by('-started_at')
        return Response(self.get_serializer(boosts, many=True).data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        boost = self.get_object()
        if boost.status != 'active':
            boost.status = 'active'
            boost.save(update_fields=['status', 'updated_at'])
        return Response(self.get_serializer(boost).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        boost = self.get_object()
        if boost.status == 'active':
            boost.status = 'cancelled'
            boost.save(update_fields=['status', 'updated_at'])
            return Response({'message': 'Boost annulé avec succès', 'status': boost.status})
        return Response(
            {'message': 'Impossible d\'annuler ce boost'},
            status=status.HTTP_400_BAD_REQUEST,
        )
