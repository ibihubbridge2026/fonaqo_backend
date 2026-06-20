"""Views pour la synchronisation des favoris clients."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction as db_transaction

from .models import FavoriteAgent
from .serializers import AgentProfileSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_favorites_list_view(request):
    """Retourne la liste des agents favoris du client connecté."""
    if not request.user.is_client:
        return Response(
            {'error': 'Réservé aux clients'},
            status=status.HTTP_403_FORBIDDEN,
        )

    favorites = FavoriteAgent.objects.filter(client=request.user).select_related('agent__agent_profile')
    agents_data = []
    for fav in favorites:
        try:
            profile = fav.agent.agent_profile
            serializer = AgentProfileSerializer(profile)
            agents_data.append(serializer.data)
        except Exception:
            continue

    return Response({
        'status': 'success',
        'data': agents_data,
        'count': len(agents_data),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def client_favorites_toggle_view(request):
    """
    Ajoute ou retire un agent des favoris du client.
    Prend agent_id dans le POST data.
    Retourne le nouveau statut booléen (is_favorite).
    """
    if not request.user.is_client:
        return Response(
            {'error': 'Réservé aux clients'},
            status=status.HTTP_403_FORBIDDEN,
        )

    agent_id = request.data.get('agent_id')
    if not agent_id:
        return Response(
            {'error': 'agent_id est requis'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        agent = User.objects.get(id=agent_id, is_agent=True)
    except User.DoesNotExist:
        return Response(
            {'error': 'Agent non trouvé'},
            status=status.HTTP_404_NOT_FOUND,
        )

    with db_transaction.atomic():
        favorite, created = FavoriteAgent.objects.get_or_create(
            client=request.user,
            agent=agent,
        )

        if not created:
            # Déjà en favori → supprimer
            favorite.delete()
            is_favorite = False
        else:
            # Nouveau favori
            is_favorite = True

    return Response({
        'status': 'success',
        'is_favorite': is_favorite,
        'agent_id': str(agent_id),
    })
