from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.views import View


class VitrineGuestCreateView(View):
    """Page vitrine — création mission sans compte mobile."""

    def get(self, request):
        return render(request, 'vitrine/creer_mission_guest.html', {
            'google_places_api_key': getattr(settings, 'GOOGLE_PLACES_API_KEY', ''),
        })


class VitrineGuestTrackView(View):
    """Page vitrine — suivi mission par code FNC-XXXX-BJ."""

    def get(self, request):
        reference = request.GET.get('ref', '').strip()
        return render(request, 'vitrine/suivi_mission_guest.html', {
            'reference': reference,
            'google_places_api_key': getattr(settings, 'GOOGLE_PLACES_API_KEY', ''),
        })


class VitrineAgentPublicView(View):
    """Page vitrine publique — profil agent (scan QR badge)."""

    def get(self, request, agent_id):
        from apps.accounts.models import AgentProfile
        from apps.core.choices import MissionStatus
        from apps.missions.models import Mission
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = get_object_or_404(User, pk=agent_id, is_agent=True)
        profile, _ = AgentProfile.objects.get_or_create(user=user)

        completed = Mission.objects.filter(
            agent=user, status=MissionStatus.COMPLETED,
        ).count()
        reviews = Mission.objects.filter(
            agent=user,
            status=MissionStatus.COMPLETED,
            client_rating__isnull=False,
        ).order_by('-updated_at')[:10]

        ratings = [m.client_rating for m in reviews if m.client_rating]
        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

        return render(request, 'vitrine/agent_public.html', {
            'agent': user,
            'profile': profile,
            'completed_missions': completed,
            'avg_rating': avg_rating,
            'reviews': reviews,
            'is_certified': profile.is_internal or profile.badge_status == 'APPROVED',
        })
