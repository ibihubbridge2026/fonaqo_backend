"""Vues API pour le programme de fidélité clients."""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from apps.accounts.loyalty_service import LoyaltyService


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
