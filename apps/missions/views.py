import logging

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import JsonResponse
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from .models import Mission, MissionTimeline, Dispute
from .serializers import MissionSerializer
from .ws_broadcast import broadcast_gps_group

logger = logging.getLogger(__name__)
from apps.accounts.permissions import IsVerifiedAgent
from apps.notifications.services import NotificationService
from apps.core.choices import MissionStatus

class MissionViewSet(viewsets.ModelViewSet):
    """
    Moteur de Mission FONAQO :
    Gère la proximité, la Timeline GPS, l'Escrow et la Sécurité.
    """
    queryset = Mission.objects.all()
    serializer_class = MissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def available(self, request):
        """
        Liste des missions disponibles (publiques) - accessible uniquement pour les agents
        """
        logger.debug("available missions user=%s is_agent=%s", request.user, request.user.is_agent)
        if not request.user.is_agent:
            return JsonResponse({
                'status': 'error',
                'message': 'Accès refusé. Cette fonctionnalité est réservée aux agents.',
                'data': {}
            }, status=status.HTTP_403_FORBIDDEN)
        queryset = Mission.objects.filter(status=MissionStatus.PENDING).select_related('client')
        
        # Filtrage par localisation si fourni
        lat = request.GET.get('lat')
        lng = request.GET.get('lng')
        
        if lat and lng:
            try:
                user_location = Point(float(lng), float(lat), srid=4326)
                queryset = queryset.annotate(
                    distance=Distance('location', user_location)
                ).order_by('distance')
            except (ValueError, TypeError):
                pass
        
        missions_data = [MissionSerializer(m).data for m in queryset]
        
        return JsonResponse({
            'status': 'success',
            'message': 'Missions disponibles récupérées',
            'data': missions_data
        })

    def get_queryset(self):
        queryset = Mission.objects.all().select_related("client", "agent")
        user = self.request.user
        lat = self.request.query_params.get('lat')
        lng = self.request.query_params.get('lng')

        if self.action == 'list':
            if getattr(user, "is_agent", False) and not getattr(user, "is_client", True):
                queryset = queryset.filter(
                    Q(status=MissionStatus.PENDING) | Q(agent=user)
                )
            elif getattr(user, "is_client", False):
                queryset = queryset.filter(client=user)
            else:
                queryset = queryset.filter(status=MissionStatus.PENDING)

        if lat and lng:
            try:
                user_location = Point(float(lng), float(lat), srid=4326)
                queryset = queryset.annotate(
                    distance=Distance('location', user_location)
                ).order_by('distance')
            except (ValueError, TypeError):
                queryset = queryset.order_by("-created_at")
        else:
            queryset = queryset.order_by("-created_at")
        return queryset

    def perform_create(self, serializer):
        # Création initiale + Première étape Timeline
        mission = serializer.save(client=self.request.user, status=MissionStatus.PENDING)
        self._add_to_timeline(mission, MissionStatus.PENDING, _("Mission publiée par le client"))

    @action(detail=True, methods=['post'], permission_classes=[IsVerifiedAgent])
    def accept(self, request, pk=None):
        """ L'agent accepte : bloque l'argent en Escrow via Signal """
        mission = self.get_object()
        if mission.status != MissionStatus.PENDING:
            return Response({"detail": _("Indisponible.")}, status=status.HTTP_400_BAD_REQUEST)
        
        mission.agent = request.user
        mission.status = MissionStatus.ACCEPTED
        mission.save()

        self._add_to_timeline(mission, MissionStatus.ACCEPTED, _("Agent assigné et fonds sécurisés"), request)
        
        NotificationService.send_to_user(
            user=mission.client,
            title=_("Agent trouvé !"),
            body=_("{} a accepté votre mission.").format(request.user.username)
        )
        broadcast_gps_group(
            str(mission.id),
            {"type": "mission_status", "status": mission.status},
        )
        return Response({"detail": _("Mission acceptée.")})

    @action(detail=True, methods=['post'], permission_classes=[IsVerifiedAgent])
    def start_mission(self, request, pk=None):
        """Passe la mission en IN_PROGRESS (suivi GPS) — réservé à l'agent assigné."""
        mission = self.get_object()
        if mission.agent != request.user:
            return Response({"detail": _("Non autorisé.")}, status=status.HTTP_403_FORBIDDEN)

        if mission.status not in (
            MissionStatus.ACCEPTED,
            MissionStatus.ON_THE_WAY,
            MissionStatus.ARRIVED,
        ):
            return Response(
                {"detail": _("Impossible de démarrer depuis ce statut.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mission.status = MissionStatus.IN_PROGRESS
        mission.save()
        self._add_to_timeline(
            mission, MissionStatus.IN_PROGRESS, _("Mission en cours (suivi GPS)."), request
        )
        broadcast_gps_group(
            str(mission.id),
            {"type": "mission_status", "status": mission.status},
        )
        NotificationService.send_to_user(
            user=mission.client,
            title=_("Mission démarrée"),
            body=_("L'agent a démarré la mission. Suivez sa position en direct."),
        )
        return Response(MissionSerializer(mission).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsVerifiedAgent])
    def mark_completed_live(self, request, pk=None):
        """Termine la mission côté agent (flux live / module tracking)."""
        mission = self.get_object()
        if mission.agent != request.user:
            return Response({"detail": _("Non autorisé.")}, status=status.HTTP_403_FORBIDDEN)

        if mission.status != MissionStatus.IN_PROGRESS:
            return Response(
                {"detail": _("La mission doit être en cours pour être clôturée.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mission.status = MissionStatus.COMPLETED
        mission.save()
        self._add_to_timeline(
            mission, MissionStatus.COMPLETED, _("Mission terminée par l'agent."), request
        )
        broadcast_gps_group(
            str(mission.id),
            {"type": "mission_status", "status": mission.status},
        )
        NotificationService.send_to_user(
            user=mission.client,
            title=_("Mission terminée"),
            body=_("L'agent a indiqué la mission comme terminée."),
        )
        return Response(MissionSerializer(mission).data, status=status.HTTP_200_OK)

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

        broadcast_gps_group(
            str(mission.id),
            {"type": "mission_status", "status": new_status},
        )

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
        
        self._add_to_timeline(mission, MissionStatus.COMPLETED, _("Preuve de travail soumise"), request)
        
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
        
        mission.status = MissionStatus.DISPUTED
        mission.save()
        
        self._add_to_timeline(mission, MissionStatus.DISPUTED, _("LITIGE OUVERT : Argent bloqué."), request)
        
        return Response({"detail": _("Litige enregistré. L'admin va trancher.")})

    def _finalize_mission(self, mission):
        """ Fermeture et Paiement """
        if mission.status == MissionStatus.COMPLETED:
            return Response(
                {"detail": _("Mission déjà finalisée.")},
                status=status.HTTP_409_CONFLICT,
            )

        mission.status = MissionStatus.COMPLETED
        mission.save()

        # Libérer le séquestre si existant
        if hasattr(mission, 'escrow') and mission.escrow:
            from apps.core.choices import EscrowStatus
            from django.utils import timezone
            escrow = mission.escrow
            if escrow.status != EscrowStatus.RELEASED:
                escrow.status = EscrowStatus.RELEASED
                escrow.released_at = timezone.now()
                escrow.save()

        self._add_to_timeline(mission, MissionStatus.COMPLETED, _("Mission validée. Fonds libérés."), self.request)

        NotificationService.send_to_user(
            user=mission.agent,
            title=_("Argent reçu !"),
            body=_("Le client a validé. Votre solde a été mis à jour.")
        )
        return Response({"status": _("Succès."), "detail": _("Mission finalisée.")})

    def _add_to_timeline(self, mission, status, message, request=None, location=None):
        """ Utilitaire pour remplir la Timeline automatiquement """
        MissionTimeline.objects.create(
            mission=mission,
            status=status,
            message=message,
            location=location,
            created_by=request.user if request else None
        )