"""Vues API pour le programme de fidélité clients."""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from apps.accounts.loyalty_service import LoyaltyService
from apps.accounts.models import RewardItem, RewardRedemption, ClientRewardProfile


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_rewards_view(request):
    """Retourne les récompenses de fidélité du client connecté.

    Response:
    {
        "status": "success",
        "data": {
            "points": 150,
            "level": 2,
            "total_missions_completed": 5,
            "total_spent": 25000.00,
            "badges_unlocked": [...],
            "available_badges": [...],
            "points_to_next_level": 200
        }
    }
    """
    if not request.user.is_client:
        return Response(
            {'status': 'error', 'message': 'Cette fonctionnalité est réservée aux clients'},
            status=status.HTTP_403_FORBIDDEN,
        )

    rewards = LoyaltyService.get_client_rewards(request.user)

    if not rewards:
        return Response(
            {'status': 'error', 'message': 'Impossible de récupérer les récompenses'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response({
        'status': 'success',
        'data': rewards,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reward_catalog_view(request):
    """Retourne le catalogue de récompenses disponibles."""
    items = RewardItem.objects.filter(is_active=True).order_by('points_cost')
    data = [{
        'id': item.id,
        'name': item.name,
        'description': item.description,
        'reward_type': item.reward_type,
        'points_cost': item.points_cost,
        'value_fcfa': float(item.value_fcfa) if item.value_fcfa else None,
        'icon': item.icon,
        'stock': item.stock,
    } for item in items]
    return Response({'status': 'success', 'data': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reward_history_view(request):
    """Retourne l'historique des redemptions du client."""
    if not request.user.is_client:
        return Response(
            {'status': 'error', 'message': 'Réservé aux clients'},
            status=status.HTTP_403_FORBIDDEN,
        )
    redemptions = RewardRedemption.objects.filter(user=request.user).select_related('reward').order_by('-created_at')
    data = [{
        'id': r.id,
        'reward_name': r.reward.name,
        'reward_icon': r.reward.icon,
        'points_spent': r.points_spent,
        'status': r.status,
        'created_at': r.created_at.isoformat(),
    } for r in redemptions]
    return Response({'status': 'success', 'data': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def redeem_reward_view(request):
    """Échange des points contre une récompense."""
    if not request.user.is_client:
        return Response(
            {'status': 'error', 'message': 'Réservé aux clients'},
            status=status.HTTP_403_FORBIDDEN,
        )

    reward_id = request.data.get('reward_id')
    if not reward_id:
        return Response(
            {'status': 'error', 'message': 'reward_id requis'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        with transaction.atomic():
            reward = RewardItem.objects.select_for_update().get(pk=reward_id, is_active=True)
            profile = ClientRewardProfile.objects.select_for_update().get(user=request.user)

            if profile.points < reward.points_cost:
                return Response(
                    {'status': 'error', 'message': f'Solde insuffisant: {profile.points} pts, requis: {reward.points_cost} pts'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if reward.stock is not None and reward.stock <= 0:
                return Response(
                    {'status': 'error', 'message': 'Récompense épuisée'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Déduire les points
            profile.deduct_points(reward.points_cost, reason=f'Redemption: {reward.name}')

            # Créer la redemption
            redemption = RewardRedemption.objects.create(
                user=request.user,
                reward=reward,
                points_spent=reward.points_cost,
                status='PENDING',
            )

            # Décrémenter le stock si limité
            if reward.stock is not None:
                reward.stock -= 1
                reward.save(update_fields=['stock'])

        return Response({
            'status': 'success',
            'message': 'Récompense échangée avec succès',
            'data': {
                'redemption_id': redemption.id,
                'new_balance': profile.points,
            }
        }, status=status.HTTP_201_CREATED)

    except RewardItem.DoesNotExist:
        return Response(
            {'status': 'error', 'message': 'Récompense introuvable'},
            status=status.HTTP_404_NOT_FOUND,
        )
    except ValueError as e:
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
