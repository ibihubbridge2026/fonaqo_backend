from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from .models import Mission, MissionTimeline, Dispute
from .serializers import MissionSerializer
from apps.accounts.permissions import IsVerifiedAgent
from apps.notifications.services import NotificationService

class MissionViewSet(viewsets.ModelViewSet):
    """
    Moteur de Mission FONAQO :
    Gère la proximité, la Timeline GPS, l'Escrow et la Sécurité.
    """
    queryset = Mission.objects.all()
    serializer_class = MissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Mission.objects.all()
        lat = self.request.query_params.get('lat')
        lng = self.request.query_params.get('lng')

        # Filtrage : Un agent ne voit que les missions PENDING (disponibles)
        if self.action == 'list':
            queryset = queryset.filter(status='PENDING')

        if lat and lng:
            try:
                user_location = Point(float(lng), float(lat), srid=4326)
                queryset = queryset.annotate(
                    distance=Distance('location', user_location)
                ).order_by('distance')
            except (ValueError, TypeError):
                pass
        return queryset

    def perform_create(self, serializer):
        # Création initiale + Première étape Timeline
        mission = serializer.save(client=self.request.user, status='PENDING')
        self._add_to_timeline(mission, 'PENDING', _("Mission publiée par le client"))

    @action(detail=True, methods=['post'], permission_classes=[IsVerifiedAgent])
    def accept(self, request, pk=None):
        """ L'agent accepte : bloque l'argent en Escrow via Signal """
        mission = self.get_object()
        if mission.status != 'PENDING':
            return Response({"detail": _("Indisponible.")}, status=status.HTTP_400_BAD_REQUEST)
        
        mission.agent = request.user
        mission.status = 'ACCEPTED'
        mission.save()

        self._add_to_timeline(mission, 'ACCEPTED', _("Agent assigné et fonds sécurisés"), request)
        
        NotificationService.send_to_user(
            user=mission.client,
            title=_("Agent trouvé !"),
            body=_("{} a accepté votre mission.").format(request.user.username)
        )
        return Response({"detail": _("Mission acceptée.")})

    @action(detail=True, methods=['post'])
    def update_steps(self, request, pk=None):
        """
        POINT 1 : Moteur de Timeline (En route, Arrivé, En cours)
        Nécessite latitude/longitude pour la preuve de présence.
        """
        mission = self.get_object()
        new_status = request.data.get('status')
        lat = request.data.get('latitude')
        lng = request.data.get('longitude')

        if mission.agent != request.user:
            return Response({"detail": _("Non autorisé.")}, status=status.HTTP_403_FORBIDDEN)

        # Validation de l'ordre logique (Optionnel mais recommandé)
        mission.status = new_status
        mission.save()

        # Capture GPS de l'étape
        location = Point(float(lng), float(lat), srid=4326) if lat and lng else None
        self._add_to_timeline(mission, new_status, f"Étape : {new_status}", request, location)

        return Response({"status": "Updated", "new_status": new_status})

    @action(detail=True, methods=['post'])
    def submit_completion(self, request, pk=None):
        """ Soumission de la preuve photo (Fin de mission) """
        mission = self.get_object()
        if mission.agent != request.user:
            return Response({"detail": _("Accès refusé.")}, status=status.HTTP_403_FORBIDDEN)
        
        if 'end_photo' not in request.FILES:
            return Response({"detail": _("Photo de preuve requise.")}, status=status.HTTP_400_BAD_REQUEST)
            
        mission.end_photo = request.FILES['end_photo']
        mission.save()
        
        self._add_to_timeline(mission, 'COMPLETED', _("Preuve de travail soumise"), request)
        
        NotificationService.send_to_user(
            user=mission.client,
            title=_("Mission terminée par l'agent"),
            body=_("Veuillez vérifier et valider pour libérer le paiement.")
        )
        return Response({"detail": _("Preuve enregistrée.")})

    @action(detail=True, methods=['post'])
    def validate_completion(self, request, pk=None):
        """ Validation finale (Libère l'argent) """
        mission = self.get_object()
        method = request.data.get('method') 
        token = request.data.get('qr_token')

        if method == 'QR_SCAN' and token == mission.qr_code_token:
            return self._finalize_mission(mission)

        if method == 'CLIENT_CLICK' and request.user == mission.client:
            return self._finalize_mission(mission)

        return Response({"detail": _("Validation échouée.")}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def open_dispute(self, request, pk=None):
        """ POINT 8 : Ouverture d'un litige """
        mission = self.get_object()
        reason = request.data.get('reason')
        
        dispute, created = Dispute.objects.get_or_create(
            mission=mission,
            defaults={'opened_by': request.user, 'reason': reason}
        )
        
        mission.status = 'DISPUTED'
        mission.save()
        
        self._add_to_timeline(mission, 'DISPUTED', _("LITIGE OUVERT : Argent bloqué."), request)
        
        return Response({"detail": _("Litige enregistré. L'admin va trancher.")})

    def _finalize_mission(self, mission):
        """ Fermeture et Paiement """
        if mission.status == 'COMPLETED':
             return Response({"detail": _("Déjà payé.")})

        mission.status = 'COMPLETED'
        mission.save()
        
        self._add_to_timeline(mission, 'COMPLETED', _("Mission validée. Fonds libérés."), self.request)
        
        NotificationService.send_to_user(
            user=mission.agent,
            title=_("Argent reçu !"),
            body=_("Le client a validé. Votre solde a été mis à jour.")
        )
        return Response({"status": _("Succès.")})

    def _add_to_timeline(self, mission, status, message, request=None, location=None):
        """ Utilitaire pour remplir la Timeline automatiquement """
        MissionTimeline.objects.create(
            mission=mission,
            status=status,
            message=message,
            location=location,
            created_by=request.user if request else None
        )