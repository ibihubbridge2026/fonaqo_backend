import logging

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction, IntegrityError
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from apps.accounts.permissions import IsAgent
from apps.core.choices import TransactionStatus
from .models import BoostPlan, AgentBoost
from .serializers import (
    BoostPlanSerializer, AgentBoostSerializer,
    AgentBoostCreateSerializer, BoostCostCalculateSerializer,
)

logger = logging.getLogger(__name__)


def _quantize_fcfa(value) -> Decimal:
    """Normalise un montant FCFA en Decimal à 2 décimales."""
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0.00')


def _resolve_boost_plan(raw_plan_id):
    """Résout un plan par ID numérique (prioritaire) ou par nom."""
    if raw_plan_id is None:
        return None
    raw = str(raw_plan_id).strip()
    if not raw:
        return None
    if raw.isdigit():
        plan = BoostPlan.objects.filter(pk=int(raw), is_active=True).first()
        if plan:
            return plan
    return BoostPlan.objects.filter(name__iexact=raw, is_active=True).first()


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
    permission_classes = [permissions.IsAuthenticated, IsAgent]

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

    @action(detail=False, methods=['post'], url_path='purchase', permission_classes=[IsAgent])
    def purchase(self, request):
        """Achat boost via solde portefeuille ou FeexPay (transaction_id)."""
        user = request.user

        plan_id = request.data.get('plan_id') or request.data.get('boost_type')
        payment_method = (request.data.get('payment_method') or 'wallet').strip().lower()
        transaction_id = request.data.get('transaction_id', '')

        plan = _resolve_boost_plan(plan_id)
        if plan is None:
            logger.error(
                'boost purchase: plan introuvable user=%s plan_id=%r boost_type=%r',
                user.id,
                request.data.get('plan_id'),
                request.data.get('boost_type'),
            )
            return Response(
                {
                    'error': 'INVALID_BOOST_PLAN',
                    'message': (
                        f'Plan de boost invalide ou inactif (identifiant reçu : {plan_id!r}).'
                    ),
                    'plan_id': plan_id,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount = _quantize_fcfa(plan.price)

        try:
            with transaction.atomic():
                if payment_method == 'wallet':
                    from apps.wallets.models import Wallet, Transaction as WalletTransaction
                    from apps.escrow.services import get_platform_wallet
                    from apps.finance import ledger_integration

                    wallet, _ = Wallet.objects.get_or_create(user=user)
                    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
                    balance = _quantize_fcfa(wallet.balance)

                    if balance < amount:
                        logger.error(
                            'boost purchase: solde insuffisant user=%s balance=%s required=%s plan_id=%s',
                            user.id,
                            balance,
                            amount,
                            plan.id,
                        )
                        return Response(
                            {
                                'error': 'INSUFFICIENT_BALANCE',
                                'message': (
                                    f'Solde insuffisant. Disponible : {balance} FCFA, '
                                    f'requis : {amount} FCFA.'
                                ),
                                'available': float(balance),
                                'required': float(amount),
                                'plan_id': plan.id,
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    platform_wallet = Wallet.objects.select_for_update().get(
                        pk=get_platform_wallet().pk,
                    )
                    wallet.balance = balance - amount
                    wallet.save(update_fields=['balance', 'updated_at'])
                    platform_wallet.balance = _quantize_fcfa(platform_wallet.balance) + amount
                    platform_wallet.save(update_fields=['balance', 'updated_at'])

                    txn_ref = f'BOOST-WALLET-{user.id}-{int(timezone.now().timestamp())}'
                    agent_txn = WalletTransaction.objects.create(
                        wallet=wallet,
                        amount=-amount,
                        transaction_type=WalletTransaction.TransactionType.BOOST_PAYMENT,
                        description=f'Achat boost {plan.name}',
                        status=TransactionStatus.COMPLETED,
                        reference=txn_ref,
                    )
                    WalletTransaction.objects.create(
                        wallet=platform_wallet,
                        amount=amount,
                        transaction_type=WalletTransaction.TransactionType.DEPOSIT,
                        description=f'Revenu boost {plan.name} — agent {user.id}',
                        status=TransactionStatus.COMPLETED,
                        reference=f'{txn_ref}-PLT',
                    )
                    ledger_integration.record_boost_wallet(
                        user_id=user.id,
                        amount=amount,
                        wallet_transaction_id=agent_txn.id,
                        reference=txn_ref,
                    )
                    transaction_id = transaction_id or txn_ref
                elif payment_method == 'feexpay':
                    if not transaction_id:
                        return Response(
                            {
                                'error': 'FEEXPAY_REFERENCE_REQUIRED',
                                'message': 'transaction_id FeexPay requis.',
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    from apps.payments.models import Payment
                    from apps.payments.services import FeexPayService
                    try:
                        FeexPayService.verify_payment(
                            user,
                            transaction_id,
                            expected_amount=amount,
                            purpose=Payment.Purpose.BOOST_PURCHASE,
                            metadata={'plan_id': plan.id, 'plan_name': plan.name},
                        )
                    except ValueError as exc:
                        logger.error(
                            'boost purchase FeexPay: user=%s plan_id=%s err=%s',
                            user.id,
                            plan.id,
                            exc,
                        )
                        return Response(
                            {
                                'error': 'FEEXPAY_VERIFICATION_FAILED',
                                'message': str(exc),
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                else:
                    return Response(
                        {
                            'error': 'INVALID_PAYMENT_METHOD',
                            'message': f'Mode de paiement invalide : {payment_method!r}.',
                        },
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
        except IntegrityError as exc:
            logger.exception(
                'boost purchase IntegrityError user=%s plan_id=%s',
                user.id,
                plan.id,
            )
            return Response(
                {
                    'error': 'BOOST_PAYMENT_FAILED',
                    'message': (
                        'Échec de l\'enregistrement du paiement boost '
                        f'(contrainte base de données : {exc}).'
                    ),
                },
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as exc:
            logger.exception(
                'boost purchase unexpected error user=%s plan_id=%s',
                user.id,
                plan.id,
            )
            return Response(
                {
                    'error': 'BOOST_PURCHASE_FAILED',
                    'message': f'Échec achat boost : {exc}',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
