from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.utils.translation import gettext_lazy as _

from .models import Mission
from .serializers import MissionSerializer
from apps.accounts.permissions import IsVerifiedAgent
from apps.notifications.services import NotificationService

class MissionViewSet(viewsets.ModelViewSet):
    """
    Gestion complète du cycle de vie des missions :
    Création, Recherche par proximité, Acceptation et Validation double-mode.
    """
    queryset = Mission.objects.all()
    serializer_class = MissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Filtre les missions et permet le tri par distance si lat/lng fournis.
        Exemple : /api/missions/?lat=6.36&lng=2.43
        """
        queryset = Mission.objects.all()
        lat = self.request.query_params.get('lat')
        lng = self.request.query_params.get('lng')

        # Par défaut, on ne montre que les missions disponibles aux agents
        if self.action == 'list':
            queryset = queryset.filter(status='PENDING')

        if lat and lng:
            try:
                user_location = Point(float(lng), float(lat), srid=4326)
                queryset = queryset.annotate(
                    distance=Distance('location', user_location)
                ).order_by('distance')
            except ValueError:
                pass
        return queryset

    def perform_create(self, serializer):
        # Le créateur est automatiquement le client connecté
        serializer.save(client=self.request.user, status='PENDING')

    @action(detail=True, methods=['post'], permission_classes=[IsVerifiedAgent])
    def accept(self, request, pk=None):
        """ 
        Un agent vérifié accepte la mission.
        Déclenche le blocage des fonds (Escrow) via signal.
        """
        mission = self.get_object()
        if mission.status != 'PENDING':
            return Response(
                {"detail": _("Cette mission n'est plus disponible.")}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        mission.agent = request.user
        mission.status = 'ACCEPTED'
        mission.save()

        # Notification au client
        NotificationService.send_to_user(
            user=mission.client,
            title=_("Mission acceptée"),
            body=_("L'agent {} est en route.").format(request.user.username)
        )
        
        return Response({"detail": _("Mission acceptée avec succès.")})

    @action(detail=True, methods=['post'])
    def submit_completion(self, request, pk=None):
        """
        MODE DISTANCIEL : L'agent soumet une preuve de fin de tâche (Photo).
        """
        mission = self.get_object()
        if mission.agent != request.user:
            return Response(
                {"detail": _("Vous n'êtes pas l'agent assigné.")}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if 'end_photo' not in request.FILES:
            return Response(
                {"detail": _("Une photo de preuve est requise.")}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        mission.end_photo = request.FILES['end_photo']
        mission.save()
        
        # Notification au client pour qu'il vienne valider sur l'app
        NotificationService.send_to_user(
            user=mission.client,
            title=_("Preuve soumise"),
            body=_("L'agent a terminé la mission. Veuillez vérifier la preuve et valider.")
        )
        return Response({"detail": _("Preuve soumise. En attente de validation du client.")})

    @action(detail=True, methods=['post'])
    def validate_completion(self, request, pk=None):
        """
        VALIDATION FINALE :
        - Soit par QR Code (Direct)
        - Soit par clic Client (Distanciel/Preuve)
        """
        mission = self.get_object()
        method = request.data.get('method')  # 'QR_SCAN' ou 'CLIENT_CLICK'
        token = request.data.get('qr_token')

        # Scénario 1 : L'agent scanne le QR Code affiché sur le téléphone du client
        if method == 'QR_SCAN':
            if token == mission.qr_code_token:
                return self._finalize_mission(mission)
            return Response({"detail": _("QR Code invalide.")}, status=status.HTTP_400_BAD_REQUEST)

        # Scénario 2 : Le client valide manuellement depuis son interface (après avoir vu la photo)
        if method == 'CLIENT_CLICK':
            if request.user == mission.client:
                return self._finalize_mission(mission)
            return Response(
                {"detail": _("Seul le client peut valider manuellement.")}, 
                status=status.HTTP_403_FORBIDDEN
            )

        return Response(
            {"detail": _("Méthode de validation non spécifiée.")}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    def _finalize_mission(self, mission):
        """
        Méthode interne pour clore la mission. 
        Le changement de statut vers COMPLETED déclenche automatiquement 
        le signal Escrow pour payer l'agent.
        """
        if mission.status == 'COMPLETED':
            return Response({"detail": _("Mission déjà terminée.")}, status=status.HTTP_400_BAD_REQUEST)

        mission.status = 'COMPLETED'
        mission.save()
        
        # Notification de succès à l'agent (le plus important : il est payé !)
        NotificationService.send_to_user(
            user=mission.agent,
            title=_("Paiement reçu !"),
            body=_("La mission est terminée. Votre compte a été crédité.")
        )
        return Response({"status": _("Mission terminée et agent payé.")})