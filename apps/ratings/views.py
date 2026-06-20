"""Views pour le système de notation."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.exceptions import ValidationError

from apps.missions.models import Mission
from apps.core.choices import MissionStatus
from .models import Rating
from .serializers import RatingSerializer


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rate_mission_view(request, mission_id):
    """
    Noter une mission terminée.
    Seul le client peut noter l'agent, et seul l'agent peut noter le client.
    La mission doit être COMPLETED.
    """
    try:
        mission = Mission.objects.get(id=mission_id)
    except Mission.DoesNotExist:
        return Response(
            {'error': 'Mission non trouvée'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if mission.status != MissionStatus.COMPLETED:
        return Response(
            {'error': 'Seules les missions terminées peuvent être notées'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Déterminer le type de notation selon le rôle de l'utilisateur
    if request.user == mission.client:
        rating_type = Rating.RatingType.CLIENT_RATES_AGENT
        reviewee = mission.agent
        if not reviewee:
            return Response(
                {'error': 'Cette mission n\'a pas d\'agent assigné'},
                status=status.HTTP_400_BAD_REQUEST,
            )
    elif request.user == mission.agent:
        rating_type = Rating.RatingType.AGENT_RATES_CLIENT
        reviewee = mission.client
    else:
        return Response(
            {'error': 'Vous n\'êtes pas autorisé à noter cette mission'},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Vérifier si l'utilisateur a déjà noté cette mission
    if Rating.objects.filter(
        mission=mission,
        reviewer=request.user,
        rating_type=rating_type,
    ).exists():
        return Response(
            {'error': 'Vous avez déjà noté cette mission'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = RatingSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Créer la notation
    rating = Rating.objects.create(
        mission=mission,
        reviewer=request.user,
        reviewee=reviewee,
        rating_type=rating_type,
        score=serializer.validated_data['score'],
        comment=serializer.validated_data.get('comment', ''),
    )

    return Response(
        RatingSerializer(rating).data,
        status=status.HTTP_201_CREATED,
    )
