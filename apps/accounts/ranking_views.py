"""Vues API pour le classement des agents."""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from apps.accounts.agent_ranking_service import AgentRankingService
from apps.accounts.serializers import AgentProfileSerializer


@api_view(['GET'])
@permission_classes([AllowAny])
def top_agents_view(request):
    """Retourne la liste des agents classés par score de classement.
    
    Query params:
    - limit: nombre d'agents à retourner (défaut: 10, max: 50)
    """
    limit = min(int(request.GET.get('limit', 10)), 50)
    
    top_profiles = AgentRankingService.get_top_agents(limit=limit)
    
    data = []
    for rank, profile in enumerate(top_profiles, start=1):
        serializer = AgentProfileSerializer(profile)
        data.append({
            'rank': rank,
            'score': round(profile.ranking_score, 2),
            'agent': serializer.data,
        })
    
    return Response({
        'status': 'success',
        'data': data,
        'count': len(data),
    }, status=status.HTTP_200_OK)
